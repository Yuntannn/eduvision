EXTRACT_PROMPT = """You are reading an image of educational content (a textbook page, worksheet, \
notes or a board).
Set has_text to true only if the image contains readable, meaningful text. In that case put a \
transcription of all of it in text, exactly as written, keeping line breaks and mathematical \
notation where you can, with no commentary.
If there is no readable, meaningful text, set has_text to false and text to an empty string."""

CLEAN_PROMPT = """You are cleaning text that was transcribed from an image.
Fix obvious recognition errors (misread characters, broken words, stray symbols) and normalise \
whitespace and formatting.
Do not add, remove or reinterpret content, and do not explain anything.
Reply with the cleaned text only."""

CLASSIFY_PROMPT = """You are an education specialist. Classify the educational content below by \
subject, topic, content type and difficulty level."""

GENERATE_PROMPT = """You are a teacher writing for students. Using the educational content and \
its classification below, produce a clear, student-friendly explanation: a title, a summary of \
2-4 sentences, 3-6 key points, 1-3 examples, and optionally a Mermaid diagram (null if a \
diagram would not help). Stay faithful to the content; do not invent facts."""
