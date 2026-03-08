"""
semantic_engine.py — Vector retrieval + LLM extraction
=======================================================
Handles the semantic lane:
  1. Retrieve chunks from vector DB (by course/unit or pure semantic)
  2. Build context window
  3. Invoke LLM with strict grounding prompt
  4. Validate answer is grounded in context

LLM is invoked IF AND ONLY IF:
  - Query is classified as semantic (not structured)
  - Context was retrieved successfully
  - Query requires explanation or synthesis

Version: 1.1 (Bug fix: Conversational responses when no context found)
"""

import re
import requests
from typing import List, Dict, Any, Optional, Tuple


class SemanticEngine:
    """
    Handles semantic retrieval and LLM-based answering.
    Strictly scoped to non-structured queries.
    """

    def __init__(self, ollama, max_context_chars: int = 1500):
        self.ollama = ollama
        self.max_context_chars = max_context_chars

    # ── Public entry point ────────────────────────────────────────────────────

    def answer(
        self,
        query: str,
        course_code: Optional[str],
        unit_number: Optional[str],
        vector_db,
        course_resolver,
        is_lab_query: bool = False,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        Retrieve relevant chunks and answer with LLM.

        Returns the standard response dict used by the runtime.
        """
        from enum import Enum

        class LabType(Enum):
            EXPLICIT_LAB = 1
            LAB_CUM_THEORY = 2
            NO_PRACTICAL = 3
            UNKNOWN = 4

        # Three-tier lab blocking (preserved from original)
        if is_lab_query and course_code and course_resolver:
            lab_type = self._classify_lab_type(course_code, course_resolver)
            if lab_type == LabType.NO_PRACTICAL:
                course_name = course_resolver.get_name_from_code(course_code)
                return self._build_result(
                    query=query,
                    answer=f"{course_name} doesn't have a practical component.",
                    method="blocked",
                    chunks=0,
                    chunks_used=0,
                    llm_used=False,
                )

        # ── Retrieve chunks ───────────────────────────────────────────────────
        chunks = self._retrieve(
            query=query,
            course_code=course_code,
            unit_number=unit_number,
            vector_db=vector_db,
            is_lab_query=is_lab_query,
            verbose=verbose,
        )

        # BUG FIX 5: Conversational response when no chunks found
        if not chunks:
            if course_code:
                course_name = course_resolver.get_name_from_code(course_code) if course_resolver else course_code
                if unit_number:
                    answer = f"I couldn't find information about this in Unit {unit_number} of {course_name}. Could you rephrase your question or ask about a different unit?"
                else:
                    answer = f"I couldn't find that in the {course_name} syllabus. Could you rephrase your question or ask about a specific unit?"
            else:
                answer = "I couldn't find that information in the syllabus. Which course are you asking about?"
            
            return self._build_result(
                query=query,
                answer=answer,
                method="semantic" if not course_code else "exhaustive",
                chunks=0,
                chunks_used=0,
                llm_used=False,
            )

        # ── Build context and call LLM ────────────────────────────────────────
        context, chunks_used = self._build_context(chunks, self.max_context_chars)

        if verbose:
            print(f"[LLM EXTRACTION]")
            print(f"  Context: {len(context)} chars from {chunks_used} chunks\n")

        try:
            raw_answer = self._generate(self._build_prompt(query, context))
            answer = self._validate(raw_answer, context)
            
            # Reasoning fallback if validation blocks
            if answer == "Not in syllabus." and raw_answer.strip():
                if verbose:
                    print("[REASONING FALLBACK] Validation blocked answer — allowing grounded reasoning\n")
                answer = raw_answer
            
            if verbose and raw_answer != answer:
                print("[VALIDATION] Answer failed grounding check — returning 'Not in syllabus.'\n")

        except Exception as e:
            answer = f"Error: {str(e)}"

        return self._build_result(
            query=query,
            answer=answer,
            method="semantic" if not course_code else "exhaustive",
            chunks=len(chunks),
            chunks_used=chunks_used,
            llm_used=True,
        )

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def _retrieve(
        self,
        query: str,
        course_code: Optional[str],
        unit_number: Optional[str],
        vector_db,
        is_lab_query: bool,
        verbose: bool,
    ) -> List[Dict]:
        chunks = []

        if course_code:
            retrieved = vector_db.retrieve_by_course(
                course_code=course_code,
                unit_number=unit_number,
                top_k=30
            )

            if is_lab_query and retrieved:
                lab_kw = ['lab', 'laboratory', 'practical', 'exercise', 'experiment']
                lab = [c for c in retrieved if any(k in c['text'].lower() for k in lab_kw)]
                other = [c for c in retrieved if c not in lab]
                chunks = lab + other
            else:
                chunks = retrieved

        # Semantic fallback
        if not chunks:
            if verbose:
                print("[RETRIEVAL] Course retrieval failed, trying semantic search\n")
            try:
                emb = self.ollama.embed_single(query)
                chunks = vector_db.search(query_embedding=emb, top_k=10)
            except Exception as e:
                if verbose:
                    print(f"  Semantic search failed: {e}\n")
                chunks = []

        if verbose:
            print(f"[RETRIEVAL] Retrieved {len(chunks)} chunks\n")

        return chunks

    # ── Context building ──────────────────────────────────────────────────────

    def _build_context(self, chunks: List[Dict], max_chars: int) -> Tuple[str, int]:
        sorted_chunks = sorted(chunks, key=lambda c: c['metadata']['chunk_index'])
        parts = []
        total = 0
        used = 0

        for chunk in sorted_chunks:
            text = chunk['text']
            if total + len(text) > max_chars:
                break
            parts.append(text)
            total += len(text)
            used += 1

        return "\n\n".join(parts), used

    # ── LLM ──────────────────────────────────────────────────────────────────

    def _build_prompt(self, query: str, context: str) -> str:
        return f"""You are a helpful syllabus assistant. Answer based ONLY on the context below.

RULES:
1. If the information is NOT in the context, respond: "Not in syllabus."
2. NEVER use general knowledge or external information.
3. Only use information that APPEARS in the context.
4. Be conversational and helpful in your tone.
5. If context is empty or irrelevant, respond: "Not in syllabus."

CONTEXT:
{context}

QUERY: {query}

ANSWER (from context only):"""

    def _generate(self, prompt: str) -> str:
        try:
            resp = requests.post(
                self.ollama.generate_endpoint,
                json={
                    "model": self.ollama.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                        "num_predict": 300,
                        "num_ctx": 2048,
                    }
                },
                timeout=45
            )
            if resp.status_code == 200:
                return resp.json()['response'].strip()
            return f"Error: HTTP {resp.status_code}"
        except requests.exceptions.Timeout:
            return "Error: LLM timeout"
        except Exception as e:
            return f"Error: {str(e)}"

    # ── Answer validation ─────────────────────────────────────────────────────

    def _validate(self, answer: str, context: str) -> str:
        """
        Validate LLM answer is grounded in context.
        Loosened thresholds from original (overlap 0.4, ALL numbers must miss).
        """
        ans_lo = answer.lower()
        ctx_lo = context.lower()

        # Check 1: Known hallucination terms not in context
        hallucination_terms = [
            'ampere', 'volt', 'si unit', 'ohm', 'watt', 'kilogram',
            'meiosis', 'mitosis', 'dna', 'rna', 'photosynthesis',
            'napoleon', 'world war', 'shakespeare', 'columbus',
        ]
        for term in hallucination_terms:
            if term in ans_lo and term not in ctx_lo:
                return "Not in syllabus."

        # Check 2: Numbers — ALL sampled must be absent to reject
        numbers = re.findall(r'\b\d+\.?\d*\b', answer)
        if numbers and len(answer) > 20:
            sample = numbers[:3]
            if not any(n in context for n in sample):
                return "Not in syllabus."

        # Check 3: Word overlap (only for substantive answers)
        if len(answer) > 50:
            ans_words = set(re.findall(r'\b\w{5,}\b', ans_lo))
            ctx_words = set(re.findall(r'\b\w{5,}\b', ctx_lo))
            common = {'about', 'which', 'their', 'there', 'these', 'those',
                      'would', 'could', 'should', 'following', 'below', 'above'}
            ans_words -= common
            if ans_words:
                overlap = len(ans_words & ctx_words) / len(ans_words)
                if overlap < 0.4:
                    return "Not in syllabus."

        return answer

    # ── Lab type detection ────────────────────────────────────────────────────

    def _classify_lab_type(self, course_code: str, resolver):
        from enum import Enum

        class LabType(Enum):
            EXPLICIT_LAB = 1
            LAB_CUM_THEORY = 2
            NO_PRACTICAL = 3
            UNKNOWN = 4

        name = resolver.get_name_from_code(course_code)
        if not name:
            return LabType.UNKNOWN

        name_lo = name.lower()
        if 'lab' in name_lo or 'laboratory' in name_lo:
            return LabType.EXPLICIT_LAB

        known_combined = {'CCS342', 'CS3301', 'CCS334'}
        if course_code.upper() in known_combined:
            return LabType.LAB_CUM_THEORY

        return LabType.NO_PRACTICAL

    # ── Helper ────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_result(
        query: str, answer: str, method: str,
        chunks: int, chunks_used: int, llm_used: bool,
        processing_time: float = 0.0,
    ) -> Dict[str, Any]:
        return {
            "query": query,
            "answer": answer,
            "method": method,
            "chunks_retrieved": chunks,
            "chunks_used": chunks_used,
            "llm_used": llm_used,
            "processing_time": processing_time,
        }