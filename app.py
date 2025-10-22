import os
import sys
import json
import httpx
from sentient_agent_framework import (
    AbstractAgent,
    DefaultServer,
    Session,
    Query,
    ResponseHandler
)
from document_loader import fetch_arxiv_abstract, fetch_pdf_text, fetch_web_text
from dotenv import load_dotenv
import asyncio
import re

load_dotenv()

def format_output(data):
    if isinstance(data, dict):
        for key in ['result', 'summary', 'text', 'answer']:
            if key in data and isinstance(data[key], str):
                return data[key].strip()
        return json.dumps(data, indent=2, ensure_ascii=False)
    if isinstance(data, list):
        return '\n'.join(format_output(item) for item in data)
    if isinstance(data, str):
        return data.strip()
    return str(data)

def call_opendeepsearch(query):
    url = os.getenv("ODP_API_URL")
    api_key = os.getenv("ODP_API_KEY")
    serper_key = os.getenv("ODP_SERPER_KEY")
    openrouter_key = os.getenv("ODP_OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY")
    log_prefix = "[ODP]"
    print(f"{log_prefix} Request for query: {query}", file=sys.stderr, flush=True)
    if not (url and api_key and serper_key and openrouter_key):
        print(f"{log_prefix} Not all config available, skipping ODP call", file=sys.stderr, flush=True)
        return "[OpenDeepSearch Used] OpenDeepSearch not configured."
    headers = {
        "X-API-KEY": api_key,
        "serper-api-key": serper_key,
        "openrouter-api-key": openrouter_key,
    }
    data = {"query": query}
    try:
        r = httpx.post(url, json=data, headers=headers, timeout=300)  # Set timeout to 5 minutes
        r.raise_for_status()
        print(f"{log_prefix} Response: {r.text[:400]}", file=sys.stderr, flush=True)
        return "[OpenDeepSearch Used]\n" + format_output(r.json())
    except Exception as e:
        print(f"{log_prefix} Error: {e}", file=sys.stderr, flush=True)
        return f"[OpenDeepSearch Used] OpenDeepSearch error: {e}"

def call_wikipedia(query):
    api_url = "https://en.wikipedia.org/api/rest_v1/page/summary/"
    search_url = "https://en.wikipedia.org/w/api.php"
    slug = query.strip().replace(' ', '_')
    try:
        r = httpx.get(api_url + slug, timeout=10)
        data = r.json()
        if "extract" in data and data["extract"]:
            return f"[Wikipedia]\n**Wikipedia Summary for [{data.get('title','')}]({data.get('content_urls',{}).get('desktop',{}).get('page','')})**\n\n{data['extract']}"
        params = {
            "action":"query", "format":"json", "list":"search", "srsearch":query
        }
        r2 = httpx.get(search_url, params=params, timeout=10)
        res2 = r2.json()
        results = res2.get("query",{}).get("search",[])
        if results:
            title = results[0]["title"]
            r3 = httpx.get(api_url + title.replace(' ','_'), timeout=10)
            data2 = r3.json()
            if "extract" in data2 and data2["extract"]:
                return f"[Wikipedia]\n**Wikipedia Summary for [{data2.get('title','')}]({data2.get('content_urls',{}).get('desktop',{}).get('page','')})**\n\n{data2['extract']}"
        return "[Wikipedia] entry not found."
    except Exception as e:
        print(f"[WIKI] Error: {e}", file=sys.stderr, flush=True)
        return f"[Wikipedia] error: {e}"

def call_arxiv(query):
    try:
        arxiv_id = None
        if "arxiv.org" in query:
            arxiv_id = query.split("arxiv.org/abs/")[-1].split()[0]
        elif query.strip().replace('.', '').isdigit():
            arxiv_id = query.strip()
        if not arxiv_id:
            return "[arXiv] No valid arXiv ID provided."
        return "[arXiv]\n" + (fetch_arxiv_abstract(arxiv_id) or "arXiv ID not found.")
    except Exception as e:
        return f"[arXiv] error: {e}"

def call_pdf_parse(query):
    try:
        pdf_url = None
        for word in query.split():
            if word.endswith(".pdf"):
                pdf_url = word
                break
        if not pdf_url:
            return "[PDF Parse] No PDF URL found in input."
        text = fetch_pdf_text(pdf_url)
        return "[PDF Parse]\n" + (text or "Could not extract PDF text.")
    except Exception as e:
        return f"[PDF Parse] error: {e}"

def call_web_fetch(query):
    try:
        url = None
        for word in query.split():
            if word.startswith("http"):
                url = word
                break
        if not url:
            return "[Web Fetch] No valid URL found in input."
        text = fetch_web_text(url)
        return "[Web Fetch]\n" + (text or "Could not extract web page.")
    except Exception as e:
        return f"[Web Fetch] error: {e}"

async def call_openrouter_llm(messages, llm_api_key, llm_model):
    headers = {"Authorization": f"Bearer {llm_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": llm_model,
        "messages": messages,
        "stream": False,
        "max_tokens": 700
    }
    async with httpx.AsyncClient(timeout=300) as client:  # Increased timeout
        r = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
        r.raise_for_status()
        return r.json()

class ResearchCopilotAgent(AbstractAgent):
    def __init__(self):
        super().__init__("Research Copilot")
        self.llm_api_key = os.getenv("OPENROUTER_API_KEY")
        self.llm_model = "mistralai/mistral-small-3.2-24b-instruct:free"
        if not self.llm_api_key:
            raise RuntimeError("Set OPENROUTER_API_KEY in your .env")
        self.memory = {}

    def get_memory(self, session_id):
        return self.memory.setdefault(session_id, [])

    def add_to_memory(self, session_id, user_prompt, agent_summary):
        self.memory.setdefault(session_id, []).append((user_prompt, agent_summary))

    async def assist(self, session: Session, query: Query, response_handler: ResponseHandler):
        prompt = query.prompt.strip()
        session_key = getattr(session, 'session_id', getattr(session, 'id', None))
        history = self.get_memory(session_key)
        stream = response_handler.create_text_stream("FINAL_RESPONSE")

        system_prompt = (
            "You are Research Copilot, a smart agent that can use multiple online tools to answer complex questions. "
            "You have available tools: "
            "- opendeepsearch: for web search, news, reviews, trending/current content\n"
            "- wikipedia: for factual or encyclopedic summaries\n"
            "- arxiv: for scientific/academic papers (ID or arxiv URL)\n"
            "- pdf_parse: for extracting and summarizing PDF documents (by URL)\n"
            "- web_fetch: for extracting and summarizing public webpages\n"
            "For each user question, decide which tool(s) to use and with what prompt."
            "Return a JSON of the tool(s) to call, with one of: wikipedia, opendeepsearch, arxiv, pdf_parse, web_fetch, and the exact prompt/query for each. Do NOT answer the question directly until tool results are provided."
        )

        messages = [{"role": "system", "content": system_prompt}]
        for q, a in history[-3:]:
            messages.append({"role": "user", "content": q})
            messages.append({"role": "assistant", "content": a.strip()[:500]})
        messages.append({"role": "user", "content": prompt})

        plan_prompt = (
            "Based on the conversation and user query, return ONLY a valid JSON like:\n"
            '[ {"tool": "opendeepsearch", "prompt": "latest in AI hardware"}, '
            '{"tool": "wikipedia", "prompt": "GPT-5"} ]\n'
            'Call all tools that are needed. Do not include any other text or answer. '
            'If summarization is needed (e.g., for long PDF/web content), pass the best summarization question as the "prompt".'
        )
        plan_messages = messages + [{"role": "user", "content": plan_prompt}]
        plan_response = await call_openrouter_llm(plan_messages, self.llm_api_key, self.llm_model)

        def _extract_json_block(s: str):
            s = (s or "").strip()

            # Strip code fences like ```json ... ``` or ``` ... ```
            s = re.sub(r'^```(?:json|JSON)?\s*', '', s)
            s = re.sub(r'```$', '', s)

            # Strip a bare leading language tag like "json\n"
            s = re.sub(r'^(?i:json)\s*', '', s)

            # Try to locate the first JSON array/object to be safe
            m = re.search(r'(\[.*\]|\{.*\})', s, flags=re.DOTALL)
            if m:
                return json.loads(m.group(1))
            # Fall back to whole string
            return json.loads(s)

        try:
            plan_content = plan_response["choices"][0]["message"]["content"]
            tool_actions = _extract_json_block(plan_content)

            # Validate shape: must be a nonempty list of dicts with a "tool" key
            if not (isinstance(tool_actions, list) and tool_actions and all(isinstance(x, dict) and "tool" in x for x in tool_actions)):
                raise ValueError("Tool plan must be a non-empty list of objects each containing a 'tool' key.")
        except Exception as exc:
            await stream.emit_chunk(
                "Tool selection LLM returned invalid JSON or error: "
                + str(exc)
                + "\nRaw:\n"
                + repr(plan_response)
            )
            await stream.complete()
            return

        tool_results = {}
        for action in tool_actions:
            tool = action.get("tool", "").strip()
            tool_prompt = action.get("prompt", "").strip()
            if tool == "opendeepsearch":
                tool_results[tool] = call_opendeepsearch(tool_prompt)
            elif tool == "wikipedia":
                tool_results[tool] = call_wikipedia(tool_prompt)
            elif tool == "arxiv":
                tool_results[tool] = call_arxiv(tool_prompt)
            elif tool == "pdf_parse":
                text = call_pdf_parse(tool_prompt)
                tool_results[tool] = await self.summarize_with_llm(text, prompt)
            elif tool == "web_fetch":
                text = call_web_fetch(tool_prompt)
                tool_results[tool] = await self.summarize_with_llm(text, prompt)
            else:
                tool_results[tool] = f"[Agent error: Tool '{tool}' not supported.]"

        aggregation_prompt = (
            "You are given results from multiple tools. Your task is to **combine these results** into a detailed, cohesive answer. "
            "Do **not summarize**; instead, **synthesize** the information into a clear, informative response that provides the best insights "
            "from each source. For each tool, you should provide relevant details, recommendations, and comparisons where applicable. "
            "Be sure to address the user's query directly, and do not leave out any essential details.\n\n"
            "User's query: " + prompt + "\n\n"
            "Tool results:\n" + "\n\n".join(f"{k}: {v}" for k, v in tool_results.items())
        )

        agg_input = messages + [{"role": "user", "content": aggregation_prompt}]
        agg_response = await call_openrouter_llm(agg_input, self.llm_api_key, self.llm_model)
        try:
            answer = agg_response["choices"][0]["message"]["content"]
        except Exception as exc:
            answer = "Error aggregating tool results: " + str(exc)
        await stream.emit_chunk(answer)
        self.add_to_memory(session_key, prompt, answer)
        await stream.complete()

    async def summarize_with_llm(self, text, user_prompt):
        if not text or len(text) < 50:
            return text
        headers = {"Authorization": f"Bearer {self.llm_api_key}", "Content-Type": "application/json"}
        llm_prompt = (
            "You are a research assistant. Summarize the following text for the given query.\n"
            f"QUERY: {user_prompt}\n\nEXTRACTED TEXT:\n{text[:3500]}"
        )
        payload = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": llm_prompt}],
            "stream": False,
            "max_tokens": 500
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
            try:
                res = r.json()
                out = res["choices"][0]["message"]["content"]
                return out if out else text
            except Exception:
                return text

if __name__ == "__main__":
    agent = ResearchCopilotAgent()
    server = DefaultServer(agent)
    server.run()
