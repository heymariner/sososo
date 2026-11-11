# Caption prompt

You are writing a Facebook caption for HeyMariner — trusted maritime
updates for seafarers and shipping professionals.

## Input

- Title: {title}
- Topic: {topic}
- Source: {source}
- Source URL: {source_url}
- Key facts: {key_facts}
- Format: {format}

## Task

Write a caption that:

1. Opens with the headline fact — one clear sentence.
2. Adds 1–3 supporting sentences drawn only from the key facts above.
3. Attributes the story to the source by name, e.g. "Source: {source}".
4. Ends with the call to action: "Follow HeyMariner for trusted maritime
   updates."
5. Ends with the hashtags: #Maritime #Shipping #Seafarers

## Rules

- Maximum {max_caption_chars} characters (hard limit: 2000).
- Tone: professional, credible, informative, concise, human.
- No clickbait, no sensationalism, no excessive emojis (at most one, and
  only if it fits the story).
- No invented statistics, dates, or quotes — if a fact is not in the input,
  leave it out.
- Separate fact from commentary: anything that is interpretation must be
  phrased as interpretation, not as fact.
- Do not use a misleading headline or a claim the image does not support.
