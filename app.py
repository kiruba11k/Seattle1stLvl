import streamlit as st
from typing import Optional, TypedDict
import os
from groq import Groq
from langgraph.graph import StateGraph, END

class ProspectMessageState(TypedDict):
    prospect_name: Optional[str]
    designation: Optional[str]
    company: Optional[str]
    industry: Optional[str]
    prospect_background: str
    my_background: Optional[str]
    final_message: Optional[str]

GROQ_API_KEY = st.secrets["GROQ_API_KEY"]    

client = Groq(api_key=GROQ_API_KEY)


def groq_llm(prompt: str, model: str = "llama3-8b-8192", temperature: float = 0.3) -> str:
    """Generate text using Groq API"""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()

def summarizer(text: str) -> str:
    """Summarize long backgrounds into key points"""
    if not text or not isinstance(text, str):
        return "No content to summarize."

    truncated_text = text[:4000]
    prompt = f"""
Create 3 concise bullet points from this background text. Focus on key professional highlights and achievements:

{truncated_text}

Bullet points:
-"""
    try:
        return groq_llm(prompt).strip()
    except Exception as e:
        print(f"Summarization error: {e}")
        return "Background summary unavailable"



def summarize_backgrounds(state: ProspectMessageState) -> ProspectMessageState:
    """Node to summarize prospect and user backgrounds"""
    return {
        **state,
        "prospect_background": summarizer(state["prospect_background"]),
        # "my_background": summarizer(state["my_background"])
    }

import re

def extract_name_from_background(background: str) -> str:
    if not background:
        return "there"
    match = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?', background)
    if match:
        return match[0]
    return "there"
def generate_message(state: ProspectMessageState) -> ProspectMessageState:
    """Node to generate LinkedIn message with event context"""
    extracted_name = extract_name_from_background(state['prospect_background'])
    prospect_first_name = extracted_name.split()[0] if extracted_name != "Unknown Prospect" else "there"
    my_name = "Sumana"  

    # Clean background: Remove company and designation references
    clean_background = re.sub(
        r'at\s+\w+\s+(\w+\s+){0,3}(of|Systems|America|Inc\.?|Ltd\.?|Corp\.?)?',
        '',
        state['prospect_background'],
        flags=re.IGNORECASE
    )
    clean_background = re.sub(
        r'\s*specializing in\s*\w+|\s*with\s+\w+\s+experience|\s*as\s+a\s+\w+',
        '',
        clean_background
    ).strip()
    clean_background = re.sub(r'\s{2,}', ' ', clean_background)  # Remove extra spaces

    prompt = f"""
IMPORTANT: Output ONLY the message itself. 
Do NOT include explanations, labels, or introductions.
Write a short LinkedIn coffee meetup message using this structure:

1. "Hi {prospect_first_name},"
2. Start with "I saw" or "I noticed" + ONE specific achievement, post, or expertise from their background (NO company names, NO job titles)
3. Then state: "I’ll be in Seattle from Aug 24 to 29" 
4. End with: "and would love to grab a coffee" + dynamic connector + dynamic discussion topic related to their expertise (Examples: "to discuss how AI is reshaping insurance", "to hear more about digital transformation trends", "and chat about your perspective on data innovation")
5. Add optional line: "Let me know if you’re up for it!"
6. Close with: "Best,\n{my_name}"

Tone: Professional, friendly, conversational. Avoid flattery words like: exploring, interested, impressive, inspiring, fascinating, noteworthy.

Examples:

Hi Jon,
I saw your leadership in driving growth and advancing healthcare outcomes through data and technology. I’ll be in Seattle from Aug 24 to 29 and would love to grab a coffee to discuss how data is reshaping the healthcare industry.
Let me know if you're up for it!
Best,
{my_name}

Hi Yoav,
I saw how you’ve scaled digital platforms by embedding AI into transport workflows—it’s a compelling lens on data-led innovation. I’ll be in Seattle from Aug 14–19 and would love to grab a coffee and chat about how AI is reshaping insurance.
Best,
{my_name}

Hi Erik,
I saw your post about ITAD Summit participation—looks like a great forum for conversations on tech leadership. I’ll be in Seattle from August 14–19 and would love to grab a coffee to hear more about your thoughts on tech leadership direction.
Let me know if you’re up for it!
Best,
{my_name}

Now create for:
Prospect: {state['prospect_name']}
Key Highlight: {clean_background}
Message (MAX 2-3 LINES within 250 chars):
Hi {prospect_first_name},"""


    try:
        response = groq_llm(prompt, temperature=0.7)
        message = response.strip()
        unwanted_starts = [
            "Here is a LinkedIn connection message",
            "Here’s a LinkedIn message",
            "LinkedIn connection message:",
            "Message:",
            "Output:"
        ]
        for phrase in unwanted_starts:
            if message.lower().startswith(phrase.lower()):
                message = message.split("\n", 1)[-1].strip()

        connection_phrases = ["look forward", "would be great", "hope to connect", "love to connect", "looking forward"]
        # if not any(phrase in message.lower() for phrase in connection_phrases):
        #     message += "\nI'll be there too & looking forward to catching up with you at the event."
        # if state['company'].lower() not in message.lower():
        #     message = message.replace(
        #         f"Hi {prospect_first_name},",
        #         f"Hi {prospect_first_name},\nI see that you will be attending  {state.get('event_name', '')}.",
        #         1
        #     )

            
        if message.count(f"Best, {my_name}") > 1:
            parts = message.split(f"Best, {my_name}")
            message = parts[0].strip() + f"\n\nBest, {my_name}"

        return {**state, "final_message": message}
    except Exception as e:
        print(f"Message generation failed: {e}")
        return {**state, "final_message": "Failed to generate message"}

workflow = StateGraph(ProspectMessageState)
workflow.add_node("summarize_backgrounds", summarize_backgrounds)
workflow.add_node("generate_message", generate_message)
workflow.set_entry_point("summarize_backgrounds")
workflow.add_edge("summarize_backgrounds", "generate_message")
workflow.add_edge("generate_message", END)
graph1 = workflow.compile()


st.set_page_config(page_title="LinkedIn Message Generator", layout="centered")
st.title(" First Level Msgs for Seattle 2025")

with st.form("prospect_form"):
    prospect_name = st.text_input("Prospect Name", "")
    designation = ""
    company = ""
    industry = ""
    prospect_background = st.text_area("Prospect Background", "Prospect professional background goes here...")
    my_background = ""
    event_name =  "Step San Francisco 2025"
    event_details = "August 12-14, MGM Grand Las Vegas"

    submitted = st.form_submit_button("Generate Message")

if submitted:
    with st.spinner("Generating message..."):
        initial_state: ProspectMessageState = {
            "prospect_name": prospect_name,
            "designation": designation,
            "company": company,
            "industry": industry,
            "prospect_background": prospect_background,
            "my_background": my_background,
            "event_name": event_name,
            "event_details": event_details,
        }
        result = graph1.invoke(initial_state)

    st.success(" Message Generated!")
    st.text_area("Final LinkedIn Message", result["final_message"], height=200, key="final_msg")

    copy_code = f"""
    <script>
    function copyToClipboard() {{
        var text = `{result['final_message']}`;
        navigator.clipboard.writeText(text).then(() => {{
            alert("Message copied to clipboard!");
        }});
    }}
    </script>
    <button onclick="copyToClipboard()"> Copy Message</button>
    """

    st.components.v1.html(copy_code, height=50)
