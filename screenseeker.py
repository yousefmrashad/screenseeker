import logging
import math
from typing import List, Optional, Tuple

from google import genai
from google.genai import types
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

from rate_limiter import generate_content_limited

logger = logging.getLogger("ScreenSeekeR")
logger.setLevel(logging.INFO)


# =====================================================================
# Pydantic Schemas for Structured JSON Output
# =====================================================================


class BoundingBox(BaseModel):
    ymin: int = Field(description="Top coordinate normalized to [0, 1000]")
    xmin: int = Field(description="Left coordinate normalized to [0, 1000]")
    ymax: int = Field(description="Bottom coordinate normalized to [0, 1000]")
    xmax: int = Field(description="Right coordinate normalized to [0, 1000]")


class GroundingResult(BaseModel):
    reasoning: str = Field(
        description="Visual reasoning leading to the target location."
    )
    found: bool = Field(
        description="True if the target is found on the screen, False otherwise."
    )
    box: Optional[BoundingBox] = Field(
        default=None,
        description="The normalized bounding box enclosing the target. Must be provided if found is True.",
    )


class VerificationResult(BaseModel):
    reasoning: str = Field(description="Analysis of the marked element in the red box.")
    result: str = Field(
        description="Must be one of 'is_target', 'target_elsewhere', or 'target_not_found'."
    )
    new_instruction: Optional[str] = Field(
        default=None, description="A clearer instruction if the target exists."
    )


class CandidateTarget(BaseModel):
    name: str = Field(
        description="Name or description of the candidate target (e.g. 'Notepad shortcut icon')."
    )
    reasoning: str = Field(
        description="Visual reasoning explaining why this matches or differs from the target description (e.g. 'This is Notepad, not Notepad++')."
    )
    box: BoundingBox = Field(
        description="Normalized bounding box [ymin, xmin, ymax, xmax] of the candidate target."
    )
    confidence: float = Field(
        description="Confidence score [0.0 to 1.0] that this matches the target description."
    )


class PlannerOutput(BaseModel):
    reasoning: str = Field(description="Step by step visual layout analysis.")
    candidates: List[CandidateTarget] = Field(
        description="List of potential targets found on the screen, ordered by confidence."
    )


# =====================================================================
# Core Configuration
# =====================================================================


class ElementConfig:
    """Configuration class for the target UI element search."""

    def __init__(
        self,
        target_name: str,
        instruction: str,
        min_size_ratio: float = 0.25,
        max_depth: int = 3,
        sigma: float = 0.3,
        iou_threshold: float = 0.3,
        model_name: str = "gemini-3.5-flash",
    ):
        self.target_name = target_name
        self.instruction = instruction
        self.min_size_ratio = min_size_ratio
        self.max_depth = max_depth
        self.sigma = sigma
        self.iou_threshold = iou_threshold
        self.model_name = model_name


# =====================================================================
# Math & Coordinate Helpers
# =====================================================================


def normalized_to_absolute(
    box: BoundingBox, width: int, height: int
) -> Tuple[int, int, int, int]:
    """
    Convert a normalized [0, 1000] bounding box to absolute pixel coordinates.

    Args:
        box: BoundingBox with ymin, xmin, ymax, xmax in [0, 1000]
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Tuple of (x1, y1, x2, y2) absolute coordinates
    """
    x1 = int((box.xmin / 1000.0) * width)
    y1 = int((box.ymin / 1000.0) * height)
    x2 = int((box.xmax / 1000.0) * width)
    y2 = int((box.ymax / 1000.0) * height)
    return x1, y1, x2, y2


def absolute_to_normalized(
    box: Tuple[int, int, int, int], width: int, height: int
) -> BoundingBox:
    """
    Convert absolute pixel coordinates to a normalized [0, 1000] bounding box.

    Args:
        box: Tuple of (x1, y1, x2, y2) absolute coordinates
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        BoundingBox in normalized [0, 1000] space
    """
    x1, y1, x2, y2 = box
    xmin = max(0, min(1000, int((x1 / width) * 1000)))
    ymin = max(0, min(1000, int((y1 / height) * 1000)))
    xmax = max(0, min(1000, int((x2 / width) * 1000)))
    ymax = max(0, min(1000, int((y2 / height) * 1000)))
    return BoundingBox(ymin=ymin, xmin=xmin, ymax=ymax, xmax=xmax)


# (calculate_iou has been removed as NMS is no longer used)


def dilate_box(
    box: Tuple[int, int, int, int],
    s_min: int,
    r_max: int,
    img_width: int,
    img_height: int,
) -> Tuple[int, int, int, int]:
    """
    Expand/dilate a bounding box (patch) to ensure context padding.

    Args:
        box: Tuple of (x1, y1, x2, y2) absolute coordinates
        s_min: Minimum side length for the box
        r_max: Context padding to add around the box
        img_width: Total image width
        img_height: Total image height

    Returns:
        Tuple of (x1_d, y1_d, x2_d, y2_d) dilated coordinates
    """
    x1, y1, x2, y2 = box
    w = x2 - x1
    h = y2 - y1

    # Apply base padding (r_max)
    x1_d = x1 - r_max
    y1_d = y1 - r_max
    x2_d = x2 + r_max
    y2_d = y2 + r_max

    w_d = x2_d - x1_d
    h_d = y2_d - y1_d

    # Expand to minimum size (s_min) if still too small
    if w_d < s_min:
        diff = s_min - w_d
        x1_d -= diff // 2
        x2_d += diff - (diff // 2)

    if h_d < s_min:
        diff = s_min - h_d
        y1_d -= diff // 2
        y2_d += diff - (diff // 2)

    # Ensure box remains within image boundaries
    x1_d = max(0, x1_d)
    y1_d = max(0, y1_d)
    x2_d = min(img_width, x2_d)
    y2_d = min(img_height, y2_d)

    return (x1_d, y1_d, x2_d, y2_d)


# =====================================================================
# Main ScreenSeekeR Class
# =====================================================================


class ScreenSeekeR:
    """The main visual search and grounding orchestration framework."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the ScreenSeekeR framework.

        Args:
            api_key: Optional Gemini API Key
        """
        self.client = genai.Client(api_key=api_key)

    def position_inference(
        self, image: Image.Image, config: ElementConfig
    ) -> List[CandidateTarget]:
        """
        Execute Step 8 of the algorithm: POSITIONINFERENCE(T, I).

        Args:
            image: PIL Image object representing screenshot/crop
            config: ElementConfig object holding search configurations

        Returns:
            List of CandidateTarget objects with confidence values
        """
        prompt = f"""You are the Planner. Analyze the screenshot and identify all potential matches for the target: '{config.target_name}' based on the instruction: '{config.instruction}'.
If there are multiple potential matches (e.g. similar looking icons, or variants like '{config.target_name}' vs other similar names/variants), locate all of them.

For each candidate:
1. Provide its bounding box [ymin, xmin, ymax, xmax] in normalized coordinates [0, 1000].
2. Provide a visual reasoning explaining why it matches or differs from the target description (e.g. explain which one is the exact match and why).
3. Assign a confidence score between 0.0 and 1.0 indicating how likely it matches the target description.

Prioritize the top candidate in the list."""

        logger.info("Executing POSITIONINFERENCE with Planner (Structured Output)...")
        try:
            response = generate_content_limited(
                client=self.client,
                model=config.model_name,
                contents=[image, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=PlannerOutput,
                    media_resolution="MEDIA_RESOLUTION_MEDIUM",
                ),
            )
            result: PlannerOutput = response.parsed
            logger.info(f"Planner Reasoning: {result.reasoning}")
            for i, c in enumerate(result.candidates):
                logger.info(
                    f"Candidate {i}: '{c.name}' (Confidence: {c.confidence}) box: {c.box}"
                )

            return result.candidates
        except Exception as e:
            logger.error(
                f"Planner position inference failed due to API/network error: {e}. Returning empty candidate list to force fallback."
            )
            return []

    def direct_grounding(
        self, image: Image.Image, config: ElementConfig
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Execute Step 6: DIRECTGROUNDING(I, viewport).

        Args:
            image: PIL Image object representing detailed crop view
            config: ElementConfig object holding search configurations

        Returns:
            Tuple of (x1, y1, x2, y2) absolute coordinates of target if found, or None.
        """
        prompt = f"""You are the Grounding model. Find the target element on the screen: '{config.target_name}'
Describe its location and state. If it exists on the screen, set 'found' to true and return its exact bounding box coordinates normalized to [0, 1000]. If it is not present, set 'found' to false and omit 'box'."""

        logger.info("Executing DIRECTGROUNDING on crop...")
        response = generate_content_limited(
            client=self.client,
            model=config.model_name,
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GroundingResult,
                media_resolution="MEDIA_RESOLUTION_HIGH",
            ),
        )
        result: GroundingResult = response.parsed
        if not result.found or result.box is None:
            logger.info(
                f"Direct Grounding failed: Target not found. Reasoning: {result.reasoning}"
            )
            return None

        abs_box = normalized_to_absolute(result.box, image.width, image.height)
        logger.info(
            f"Direct Grounding Result: {abs_box} (Reasoning: {result.reasoning})"
        )
        return abs_box

    def verify_prediction(
        self, image: Image.Image, box: Tuple[int, int, int, int], config: ElementConfig
    ) -> bool:
        """
        Verify if the predicted bounding box contains the target element.

        Args:
            image: Parent PIL Image
            box: Tuple of (x1, y1, x2, y2) absolute bounding box coordinates
            config: ElementConfig holding verification prompts and parameters

        Returns:
            True if prediction matches the target, False otherwise
        """
        # Crop around target with a 20% margin to give context to verification
        x1, y1, x2, y2 = box
        w, h = x2 - x1, y2 - y1
        margin_x = int(w * 0.2)
        margin_y = int(h * 0.2)

        crop_x1 = max(0, x1 - margin_x)
        crop_y1 = max(0, y1 - margin_y)
        crop_x2 = min(image.width, x2 + margin_x)
        crop_y2 = min(image.height, y2 + margin_y)

        crop_img = image.crop((crop_x1, crop_y1, crop_x2, crop_y2))

        # Draw a red bounding box around the target relative to the crop
        draw_img = crop_img.copy()
        draw = ImageDraw.Draw(draw_img)
        draw.rectangle(
            [x1 - crop_x1, y1 - crop_y1, x2 - crop_x1, y2 - crop_y1],
            outline="red",
            width=2,
        )

        prompt = f"""You are given a cropped screenshot. Your task is to evaluate whether the marked element in the red box matches the target described in my instruction.
Please follow these steps:
1. Analyze the screenshot by describing its visible content and functionalities.
2. Determine which of the following applies:
- 'is_target': The marked element is the target.
- 'target_elsewhere': The marked element is not the target, but it exists elsewhere.
- 'target_not_found': The marked element is not the target, and it does not exist.
3. If the target exists, rewrite the instruction to make it clearer.

After your analysis, provide the result in JSON format matching the schema.

Here is my instruction:
{config.instruction}"""

        logger.info("Executing verification check...")
        try:
            response = generate_content_limited(
                client=self.client,
                model=config.model_name,
                contents=[draw_img, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=VerificationResult,
                    media_resolution="MEDIA_RESOLUTION_HIGH",
                ),
            )
            verification: VerificationResult = response.parsed
            logger.info(
                f"Verification Decision: {verification.result} (Reason: {verification.reasoning})"
            )
            return verification.result == "is_target"
        except Exception as e:
            logger.error(f"Verification failed: {e}. Defaulting to True to try action.")
            return True

    def visual_search(
        self, image: Image.Image, config: ElementConfig, depth: int = 0
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Execute recursive visual search (Algorithm 1 ScreenSeekeR).

        Args:
            image: PIL Image object representing search canvas
            config: ElementConfig object holding configurations
            depth: Current recursion depth

        Returns:
            Tuple of (x1, y1, x2, y2) absolute coordinates of element if found, or None
        """
        img_w, img_h = image.size
        logger.info(f"VISUALSEARCH (depth={depth}) on Image size: {img_w}x{img_h}")

        # Compute dynamic sizes based on current screenshot size
        s_min = max(256, int(min(img_w, img_h) * config.min_size_ratio))
        r_max = max(16, int(math.sqrt(img_w**2 + img_h**2) * 0.05))

        # Base Case: depth limit or image is too small to crop further
        if depth >= config.max_depth or img_w <= s_min or img_h <= s_min:
            logger.info("Base case reached. Running direct grounding.")
            box = self.direct_grounding(image, config)
            if box is not None and self.verify_prediction(image, box, config):
                return box
            return None

        # Step 8: POSITIONINFERENCE - Planner identifies candidate bounding boxes directly
        candidates = self.position_inference(image, config)

        if not candidates:
            logger.info("No candidates proposed by planner. Running direct grounding.")
            box = self.direct_grounding(image, config)
            if box is not None and self.verify_prediction(image, box, config):
                return box
            return None

        # Step 9: Convert candidate targets to absolute coordinates and dilate to form patches
        # Rely on the LLM's confidence scores directly to order candidates, with NMS removed.
        candidate_patches = []
        for c in candidates:
            abs_box = normalized_to_absolute(c.box, img_w, img_h)
            patch = dilate_box(abs_box, s_min, r_max, img_w, img_h)
            candidate_patches.append((patch, c.confidence))

        # Sort candidates descending by confidence score
        candidate_patches.sort(key=lambda x: x[1], reverse=True)
        sorted_patches = [patch for patch, score in candidate_patches]

        logger.info(f"Ranked search patches: {sorted_patches}")

        # Step 14-20: Loop and recursively crop and search
        for patch in sorted_patches:
            px1, py1, px2, py2 = patch
            pw, ph = px2 - px1, py2 - py1

            # Prevent cropping the entire image repeatedly to avoid infinite recursion
            if pw >= img_w * 0.95 and ph >= img_h * 0.95:
                continue

            logger.info(f"Cropping region {patch} and recursing...")
            sub_image = image.crop((px1, py1, px2, py2))

            # Recurse
            res_box = self.visual_search(sub_image, config, depth + 1)

            if res_box is not None:
                # Project coordinates back to parent image coordinate space
                rx1, ry1, rx2, ry2 = res_box
                parent_box = (px1 + rx1, py1 + ry1, px1 + rx2, py1 + ry2)
                logger.info(f"Found target bounding box: {parent_box}")
                return parent_box

        # Step 21: return None if all search branches fail
        return None
