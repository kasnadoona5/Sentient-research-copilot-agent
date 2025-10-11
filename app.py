import os
import sys
import json
from sentient_agent_framework import AbstractAgent, DefaultServer, Session, Query, ResponseHandler
from document_loader import fetch_arxiv_abstract, fetch_pdf_text, fetch_web_text
import httpx
from dotenv import load_dotenv

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
        return None
    headers = {
        "X-API-KEY": api_key,
        "serper-api-key": serper_key,
        "openrouter-api-key": openrouter_key,
    }
    data = {"query": query}
    try:
        r = httpx.post(url, json=data, headers=headers, timeout=30)
        r.raise_for_status()
        print(f"{log_prefix} Response: {r.text[:400]}", file=sys.stderr, flush=True)
        return r.json()
    except Exception as e:
        print(f"{log_prefix} Error: {e}", file=sys.stderr, flush=True)
        return None

def call_wikipedia(query):
    api_url = "https://en.wikipedia.org/api/rest_v1/page/summary/"
    search_url = "https://en.wikipedia.org/w/api.php"
    slug = query.strip().replace(' ', '_')
    try:
        r = httpx.get(api_url + slug, timeout=10)
        data = r.json()
        if "extract" in data and data["extract"]:
            return f"**Wikipedia Summary for [{data.get('title','')}]({data.get('content_urls',{}).get('desktop',{}).get('page','')})**\n\n{data['extract']}"
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
                return f"**Wikipedia Summary for [{data2.get('title','')}]({data2.get('content_urls',{}).get('desktop',{}).get('page','')})**\n\n{data2['extract']}"
        return None
    except Exception as e:
        print(f"[WIKI] Error: {e}", file=sys.stderr, flush=True)
        return None

class ResearchCopilotAgent(AbstractAgent):
    def __init__(self):
        super().__init__("Research Copilot")
        self.llm_api_key = os.getenv("OPENROUTER_API_KEY")
        self.llm_model = "mistralai/mistral-small-3.2-24b-instruct:free"
        assert self.llm_api_key, "Set OPENROUTER_API_KEY in your .env"

    async def decide_tool_llm(self, user_prompt):
        """
        Ask the LLM if the question is best answered from Wikipedia or OpenDeepSearch.
        Expects LLM to answer as: "WIKI" or "ODP"
        """
        prompt = (
            "You are a smart agent router. Decide which source is best to answer the user query:\n"
            "- If the answer can be found as a static factual summary or entity on Wikipedia, reply with ONLY 'WIKI'.\n"
            "- If the answer requires dynamic, recent, news, product prices, lists, reviews, data, web articles, or anything that Wikipedia likely doesn't cover, reply with ONLY 'ODP'.\n"
            "- User Query: " + user_prompt
        )
        headers = {"Authorization": f"Bearer {self.llm_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": 10
        }
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=30)
                result = r.json()
                if isinstance(result, dict) and 'choices' in result and result['choices']:
                    tool = result['choices'][0]['message']['content'].strip().upper()
                    if tool in ("WIKI", "ODP"):
                        return tool
                print("[ROUTER LLM RESPONSE ERROR]", result, file=sys.stderr, flush=True)
                return "ODP"
        except Exception as e:
            print(f"[ROUTER LLM ERROR] {e}", file=sys.stderr, flush=True)
            return "ODP"

    async def assist(self, session: Session, query: Query, response_handler: ResponseHandler):
        prompt = query.prompt.strip()
        url, arxiv_id, pdf_url = None, None, None

        stream = response_handler.create_text_stream("response")
        print(f"[DEBUG] >>> Prompt: {prompt}", file=sys.stderr, flush=True)

        try:
            # Extraction logic
            if "arxiv.org" in prompt:
                arxiv_id = prompt.split("arxiv.org/abs/")[-1].split()[0]
                print(f"[DEBUG] Detected arxiv ID: {arxiv_id}", file=sys.stderr, flush=True)
            elif ".pdf" in prompt:
                pdf_url = [word for word in prompt.split() if word.endswith(".pdf")][0]
                print(f"[DEBUG] Detected PDF URL: {pdf_url}", file=sys.stderr, flush=True)
            elif "http" in prompt:
                url = [word for word in prompt.split() if word.startswith("http")][0]
                print(f"[DEBUG] Detected URL: {url}", file=sys.stderr, flush=True)

            content = None
            error_msg = None
            if arxiv_id:
                content = fetch_arxiv_abstract(arxiv_id)
                if not content:
                    error_msg = "Could not fetch arxiv abstract. Is the ID correct?"
            elif pdf_url:
                content = fetch_pdf_text(pdf_url)
                if not content:
                    error_msg = f"Could not fetch or parse PDF: {pdf_url}. Is it a valid, accessible PDF?"
            elif url:
                content = fetch_web_text(url)
                if not content:
                    error_msg = f"Could not fetch or parse web page: {url}."

            print(f"[DEBUG] Extracted content (first 200): {(content or '')[:200]}", file=sys.stderr, flush=True)

            # Use LLM to route between Wikipedia and OpenDeepSearch
            if not content:
                tool = await self.decide_tool_llm(prompt)
                if tool == "WIKI":
                    wiki_result = call_wikipedia(prompt)
                    if wiki_result:
                        await stream.emit_chunk(wiki_result)
                    else:
                        await stream.emit_chunk("No Wikipedia result found. Try rephrasing, or ask a more general question.")
                else:
                    odp_result = call_opendeepsearch(prompt)
                    if odp_result:
                        odp_text = format_output(odp_result)
                        await stream.emit_chunk(f"[OpenDeepSearch Result]\n\n{odp_text}")
                    else:
                        await stream.emit_chunk("Could not extract content and no external search result. Please retry with a valid link or different topic.")
                await stream.complete()
                print(f"[ERROR] No content extracted (LLM router: {tool})", file=sys.stderr, flush=True)
                return

        except Exception as ex:
            await stream.emit_chunk(f"Extraction error: {str(ex)}")
            await stream.complete()
            print(f"[ERROR] Exception during extraction: {ex}", file=sys.stderr, flush=True)
            return

        # LLM call for summary
        await self.summarize_and_stream(content, prompt, stream)

    async def summarize_and_stream(self, content, user_prompt, stream):
        system_msg = (
            "You are a research assistant. Given the following TEXT, produce a summary, highlight key points, and organize findings in bullet points. Only use information from the text."
        )
        llm_prompt = f"{system_msg}\n\nTEXT:\n{content[:3500]}\n\nUserInstruction: {user_prompt}"

        headers = {"Authorization": f"Bearer {self.llm_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": llm_prompt}],
            "stream": False,
            "max_tokens": 700
        }
        print("[DEBUG] LLM payload built, sending request...", file=sys.stderr, flush=True)
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=60)
                print(f"[DEBUG] LLM HTTP status: {r.status_code}", file=sys.stderr, flush=True)
                result = r.json()
                summary = ""
                if isinstance(result, dict) and 'choices' in result and result['choices']:
                    summary = result["choices"][0]["message"]["content"]
                    formatted = format_output(summary)
                    await stream.emit_chunk(formatted)
                else:
                    await stream.emit_chunk(f"LLM call failed or returned no choices. Raw response:\n{format_output(result)}")
        except Exception as e:
            await stream.emit_chunk(f"Error from LLM: {str(e)}")
            print(f"[ERROR] Exception in summarize_and_stream: {e}", file=sys.stderr, flush=True)
        await stream.complete()

if __name__ == "__main__":
    agent = ResearchCopilotAgent()
    server = DefaultServer(agent)
    server.run()
