You are the Planner. Analyze the screenshot and identify all potential matches for the target: '{config.target_name}' based on the instruction: '{config.instruction}'.
If there are multiple potential matches (e.g. similar looking icons, or variants like '{config.target_name}' vs other similar names/variants), locate all of them.

For each candidate:
1. Provide its bounding box [ymin, xmin, ymax, xmax] in normalized coordinates [0, 1000].
2. Provide a visual reasoning explaining why it matches or differs from the target description (e.g. explain which one is the exact match and why).
3. Assign a confidence score between 0.0 and 1.0 indicating how likely it matches the target description.

Prioritize the top candidate in the list.
