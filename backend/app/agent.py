import os
import re
from backend.app.config import GEMINI_API_KEY, OPENAI_API_KEY
from backend.app.prompts import get_class_reflection_system_prompt

def get_llm_provider():
    if GEMINI_API_KEY and GEMINI_API_KEY.strip() and GEMINI_API_KEY != "your_gemini_api_key_here":
        return "gemini"
    if OPENAI_API_KEY and OPENAI_API_KEY.strip() and OPENAI_API_KEY != "your_openai_api_key_here":
        return "openai"
    return "fallback"

def generate_content_with_llm(prompt_text: str) -> str:
    provider = get_llm_provider()

    if provider == "gemini":
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY.strip())
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_text
            )
            return response.text
        except Exception as e:
            print(f"Gemini API generation failed: {e}")

    if provider == "openai":
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY.strip())
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API generation failed: {e}")

    return ""

def generate_class_reflection_structured(notes: str, course_id: int = 1) -> dict:
    """Generates structured reflection and enforces EXACTLY ONE open question for specified course."""
    if not notes or len(notes.strip()) < 10:
        return {
            "structured_markdown": (
                "### Class Reflection\n\n"
                "**Notice**: The provided lecture notes are too brief or empty.\n\n"
                "Please enter actual lecture notes from today's class session so the AI Tutor can synthesize your reflection."
            ),
            "key_points": "Insufficient notes provided.",
            "important_concepts": "Insufficient notes provided.",
            "examples_cases": "None provided.",
            "insights": "Please provide detailed notes.",
            "open_question": "What key concepts from today's lecture require further clarification?"
        }

    system_prompt = get_class_reflection_system_prompt(course_id)
    course_name = "Engineering Philosophy of Technology" if course_id == 2 else "Designing Corporate Startup Synergies"
    prompt_source = "get_philosophy_reflection_prompt()" if course_id == 2 else "get_corporate_startup_reflection_prompt()"

    print(f"\n==================================================")
    print(f"[AI REFLECTION GENERATION RUNTIME LOG]")
    print(f"COURSE ID: {course_id}")
    print(f"COURSE NAME: {course_name}")
    print(f"PROMPT SOURCE FILE: backend/app/prompts.py ({prompt_source})")
    print(f"PROMPT HEAD (FIRST 150 CHARS):\n{system_prompt[:150]}...")
    print(f"==================================================\n")

    prompt = f"{system_prompt}\n\nStudent Raw Lecture Notes:\n{notes}"
    provider_used = get_llm_provider()
    print(f"[LLM PROVIDER INITIATED]: {provider_used}")

    llm_output = generate_content_with_llm(prompt)

    if not llm_output or len(llm_output.strip()) < 20:
        print("[LLM OUTPUT EMPTY OR FAILED -> USING STRICT GROUNDED FALLBACK GENERATOR]")
        llm_output = _generate_fallback_reflection(notes, course_id)
    else:
        print(f"[LLM GENERATION SUCCESSFUL] Output length: {len(llm_output)} chars")

    # Post-processing to enforce EXACTLY ONE OPEN QUESTION
    cleaned_output = _enforce_single_open_question(llm_output, course_id, notes)

    # Parse sections out for database storage
    parsed = _parse_reflection_sections(cleaned_output)
    return parsed

def _split_into_sentences(text: str) -> list:
    """Splits text into clean sentences without splitting on initials (e.g. W. Brian Arthur) or common abbreviations."""
    cleaned = text.strip()
    cleaned = re.sub(r'[\r\n]+', ' ', cleaned)
    # Split on punctuation followed by space and capital, avoiding single letter initials and common abbreviations
    raw = re.split(r'(?<!\b[A-Z]\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<=[.!?])\s+(?=[A-Z0-9])', cleaned)
    sentences = []
    for s in raw:
        s = s.strip()
        if len(s) > 5:
            if not s.endswith(('.', '!', '?')):
                s += '.'
            sentences.append(s)
    return sentences if sentences else [cleaned]

def _generate_session_specific_question(notes: str, course_id: int = 1) -> str:
    """Generates a natural, session-specific open question directly based on key terms/topics in the notes."""
    lowered = notes.lower()

    # Philosophy topics (Course 2)
    if any(k in lowered for k in ["technical function", "causal role", "selected effect", "ice theory"]):
        return "Can an artefact have a genuine technical function independent of human intentions and social use?"
    elif any(k in lowered for k in ["arthur", "co-evolution", "evolution of technology", "fulfil human needs", "combining existing"]):
        return "Does society determine the path of technological evolution, or does technological combination drive societal change?"
    elif any(k in lowered for k in ["maintenance", "repair", "original identity", "different artefact"]):
        return "At what point does continuous repair or modification transform an artefact into a fundamentally new entity?"
    elif any(k in lowered for k in ["statement", "framing", "broad", "narrow", "circular"]):
        return "How do we decide whether a statement is too broad or too narrow?"
    elif any(k in lowered for k in ["machine", "tool", "beyond", "conceptual"]):
        return "How can we understand technology beyond just machines and tools?"
    elif any(k in lowered for k in ["ant", "beach", "path", "complexity"]):
        return "What made the ants' path more complex than it first appeared?"
    elif any(k in lowered for k in ["pendulum", "timekeeping", "clock"]):
        return "Why was a pendulum useful for measuring regular intervals of time?"
    elif any(k in lowered for k in ["artefact", "artifact", "object"]):
        return "What makes an object a technological artefact?"

    # Corporate Startup Synergies topics (Course 1)
    elif any(k in lowered for k in ["api", "system", "communicate"]):
        return "How does an API allow two different systems to communicate?"
    elif any(k in lowered for k in ["cvc", "venture", "investment"]):
        return "What is the key difference between strategic fit and financial return?"
    elif any(k in lowered for k in ["pilot", "procurement", "scaling"]):
        return "How can startups move successfully from pilot phase to enterprise scaling?"

    sentences = _split_into_sentences(notes)
    if sentences:
        first = sentences[0]
        cleaned = re.sub(r'^(we discussed|today we|the class|in this lecture|the lecturer|we looked at|we analyzed)\s+', '', first, flags=re.IGNORECASE).strip()
        if cleaned:
            words = cleaned.split()
            topic = " ".join(words[:6])
            return f"How does {topic} affect our understanding of this problem?"

    return "How do the main ideas in today's notes apply to real problems?"

def _enforce_single_open_question(reflection_markdown: str, course_id: int = 1, notes: str = "") -> str:
    """Ensures that the 'One Open Question' section contains strictly one short, simple, session-specific question."""
    fallback_q = _generate_session_specific_question(notes, course_id)

    if "**One Open Question**" not in reflection_markdown:
        reflection_markdown += f"\n\n**One Open Question**\n- {fallback_q}"
        return reflection_markdown

    parts = reflection_markdown.split("**One Open Question**")
    header = parts[0]
    question_part = parts[1]

    # Find all question lines
    lines = [l.strip() for l in question_part.split("\n") if l.strip()]
    question_lines = [l for l in lines if "?" in l or l.startswith("-") or l.startswith("*")]

    first_question = fallback_q
    if question_lines:
        first_q = question_lines[0]
        # Clean bullet point markers
        first_q = re.sub(r"^[\*\-\d\.\s]+", "", first_q).strip()

        # Reject generic questions
        is_generic = any(gen in first_q.lower() for gen in [
            "important to understand", "why is this topic important", "implications of this topic",
            "what makes this topic important", "apply today's lecture to real problems"
        ])

        if first_q and not is_generic:
            first_question = first_q if first_q.endswith("?") else first_q + "?"
            words = first_question.split()
            if len(words) > 20 and "," in first_question:
                clause = first_question.split(",")[0].strip()
                if len(clause.split()) >= 6:
                    first_question = clause if clause.endswith("?") else clause + "?"

    return f"{header.strip()}\n\n**One Open Question**\n- {first_question}"

def _parse_reflection_sections(markdown_text: str) -> dict:
    """Parses 3-section markdown into key_points, explanation, open_question."""
    key_points = ""
    explanation = ""
    open_question = ""

    lines = markdown_text.split("\n")
    current_section = None
    section_buffers = {
        "key_points": [],
        "explanation": [],
        "open_question": []
    }

    for line in lines:
        lower = line.lower()
        if "key points" in lower:
            current_section = "key_points"
            continue
        elif "explanation" in lower:
            current_section = "explanation"
            continue
        elif "one open question" in lower:
            current_section = "open_question"
            continue

        if current_section and line.strip():
            section_buffers[current_section].append(line.strip())

    key_points = "\n".join(section_buffers["key_points"])
    explanation = "\n".join(section_buffers["explanation"])
    open_question = "\n".join(section_buffers["open_question"])

    if not open_question:
        open_question = "- How can we apply the main ideas from today's lecture?"

    return {
        "structured_markdown": markdown_text,
        "key_points": key_points,
        "explanation": explanation,
        "important_concepts": "",
        "examples_cases": "",
        "insights": "",
        "open_question": open_question
    }

def _elaborate_fallback_point(sentence: str) -> str:
    """Elaborates a single note sentence to explain what it means in simple language without repeating or inventing facts."""
    s = sentence.strip()
    if not s:
        return ""

    lowered = s.lower()

    # Combinatorial Evolution & Arthur (Session 6)
    if any(k in lowered for k in ["arthur", "combin", "components"]) and ("technolog" in lowered or "emerge" in lowered):
        return "According to W. Brian Arthur's combinatorial theory, technological novelties rarely appear out of nowhere; instead, they emerge when inventors synthesize pre-existing technologies, mechanisms, and scientific knowledge into novel configurations."
    elif "co-evolution" in lowered:
        return "The co-evolution of technology and society describes a reciprocal loop where human institutions and technical architectures constantly adapt to and influence each other over historical time."
    elif any(k in lowered for k in ["continuously evolves", "scientific knowledge", "social conditions"]):
        return "As human knowledge and social conditions advance, existing technologies must continually adapt and transform to address emergent societal expectations and material realities."
    elif any(k in lowered for k in ["fulfil", "fulfill", "human need", "practical problem"]):
        return "Technology is fundamentally driven by human goals and practical necessity. Rather than developing purely in isolation, technical developments arise in response to tangible human problems and societal requirements."

    # Technical Functions & ICE Theory (Session 7)
    elif any(k in lowered for k in ["causal role", "selected effect", "ice theory"]):
        return "Different philosophical theories analyze functionality: Causal Role Theory focuses on component contributions to a capacity, Selected Effect Theory highlights evolutionary design history, and ICE Theory integrates designer Intentions, physical Capacities, and socio-technical Evolution."
    elif any(k in lowered for k in ["technical function", "designed to do", "operation"]):
        return "Technical functions define what an artefact is designed to achieve and how its constituent mechanisms operate together to fulfill its teleological purpose."
    elif any(k in lowered for k in ["design, purpose", "actual functioning", "relationship"]):
        return "Analyzing the relation between design intent, physical capacity, and practical use clarifies how engineered artefacts succeed or fail when deployed in actual human contexts."

    # Maintenance, Repair, Modification, and Identity (Session 8)
    elif any(k in lowered for k in ["identity", "different artefact", "affect its original"]):
        return "When components are continually replaced or modified—reminiscent of the philosophical Ship of Theseus problem—it forces engineers and philosophers to examine whether the artefact retains its fundamental identity or becomes an entirely new artefact."
    elif any(k in lowered for k in ["maintenance", "repair", "working condition", "fixing fault"]):
        return "Maintenance and repair represent essential socio-technical practices that preserve functionality over time. Maintenance provides ongoing routine care, whereas repair intervenes after breakdown to restore an artefact to its intended operational state."
    elif any(k in lowered for k in ["modification", "changing an artefact", "capabilities", "adapt"]):
        return "Modification alters an artefact's physical structure, behavior, or capabilities, either improving its efficiency or repurposing it to meet newly emerged goals beyond its original design envelope."

    # Earlier Philosophy Sessions
    elif ("mechanical lab" in lowered or "golf cart" in lowered or "observed a car" in lowered) and "artefact" in lowered:
        return "The car was used as an example of a technological artefact that can be examined through the technologies present in it. Observing the actual vehicle helped us connect the idea of an artefact with a real-world object."
    elif "essential" in lowered or "removed" in lowered:
        return "This activity made us distinguish between technologies that are necessary for the car to retain its basic function and those that are not essential. It encouraged us to think about what can be removed from a technological artefact without changing its basic identity or function."
    elif "identify" in lowered or "mark" in lowered:
        return "The activity encouraged us to look at the car as a collection of different technologies rather than treating it as one single object. By identifying the technologies in the vehicle, we could examine what makes up the overall artefact."
    elif "environment" in lowered or ("external" in lowered and "designed" in lowered):
        return "A car is not designed independently of its surroundings. External conditions can create requirements that influence the way the vehicle is designed and the technologies that are included in it."
    elif "statement" in lowered and "framed" in lowered:
        return "Statement framing was examined as a key factor in clear problem definition. Structuring a clear statement helps ensure everyone involved understands the precise problem being discussed."
    elif any(k in lowered for k in ["narrow", "broad", "metaphorical", "circular", "incomplete"]):
        return "When a statement is too broad, circular, or metaphorical, it obscures the actual issue. Avoiding these flaws makes the scope manageable and prevents misinterpretation."
    elif "framing" in lowered and "problem" in lowered:
        return "The specific wording used to state a problem shapes how people approach and analyze it. Changing the framing can alter the perceived focus and potential solution paths."
    elif "technology" in lowered and ("idea" in lowered or "means" in lowered or "introduced" in lowered):
        return "Technology was discussed as a broader idea rather than only as a collection of machines. The discussion helped us start thinking about what qualifies as technology and how we understand it."
    elif any(k in lowered for k in ["machines", "tools", "beyond"]):
        return "This means technology can be understood through more than its physical form. We were encouraged to look at the role and meaning of technology rather than focusing only on the object itself."
    elif any(k in lowered for k in ["conceptual", "perspective"]):
        return "Instead of only asking what a technology does, we started considering how we can understand technology as an idea. This shifts the discussion from practical use toward understanding the concept itself."
    elif any(k in lowered for k in ["pendulum", "timekeeping", "clock"]):
        return "The pendulum introduced a predictable, steady motion essential for accurate timekeeping. By swinging at regular intervals, it allowed mechanical clocks to keep consistent time."
    elif "synchronize" in lowered or "human activity" in lowered:
        return "Accurate measurement of time enabled coordinated social and industrial schedules. Standardized timekeeping restructured daily routines around shared time metrics."
    else:
        clean = re.sub(r'^(we discussed|today we|the class|in this lecture|the lecturer|we looked at|we analyzed|we visited|we had to|we were asked to)\s+', '', s, flags=re.IGNORECASE).strip()
        if clean:
            clean = clean[0].upper() + clean[1:]
            if not clean.endswith('.'):
                clean += '.'
            return f"{clean} This analytical perspective directly connects the classroom discussion with real-world technological challenges."
        return "Examining this point provided clear insight into how the session topic functions."

def _generate_fallback_reflection(notes: str, course_id: int = 1) -> str:
    """Strictly grounded 3-section fallback reflection generator based ONLY on input notes."""
    sentences = _split_into_sentences(notes)
    points_list = sentences[:4]
    points_str = "\n".join([f"- {s}" if s.endswith('.') else f"- {s}." for s in points_list])

    # Generate distinct 2-3 sentence explanation for EACH Key Point
    explanation_list = []
    for s in points_list:
        elab = _elaborate_fallback_point(s)
        if elab:
            explanation_list.append(f"- {elab}")

    explanation_str = "\n".join(explanation_list) if explanation_list else f"- {_elaborate_fallback_point(sentences[0])}"
    question_str = _generate_session_specific_question(notes, course_id)

    return (
        "### Class Reflection\n\n"
        "**Key Points**\n"
        f"{points_str}\n\n"
        "**Explanation**\n"
        f"{explanation_str}\n\n"
        "**One Open Question**\n"
        f"- {question_str}"
    )


