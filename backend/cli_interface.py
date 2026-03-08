"""
cli_interface.py — Interactive CLI
====================================
Version: CLEAN (no default session override)
"""

import re


class InteractiveInterface:
    def __init__(self, rag_system):
        self.rag = rag_system

        if self.rag.session_manager:
            self.session = self.rag.session_manager.create_session()
            self.session_id = self.session.session_id
            print(f"✓ Session created: {self.session_id[:8]}...\n")
        else:
            self.session_id = None

    def _prompt_department(self) -> None:
        available = self.rag.get_available_departments()

        print("=" * 70)
        if available:
            print(f"Available departments: {', '.join(available)}")
        else:
            print("No departments found on disk. Enter a department code manually.")
        print("=" * 70)

        while True:
            try:
                raw = input("Select department (e.g., CSE, ECE, EEE): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n👋 Goodbye!\n")
                raise SystemExit(0)

            if not raw:
                continue
            if raw.lower() in {'quit', 'exit', 'q'}:
                print("\n👋 Goodbye!\n")
                raise SystemExit(0)

            result = self.rag.set_department(raw, session_id=self.session_id)
            if result["ok"]:
                print(f"✓ Department set to {result['department']}\n")
                return
            print(f"❌ {result['error']}")

    def run(self):
        self._prompt_department()

        print("\n" + "=" * 70)
        print("INTERACTIVE QUERY MODE (v5.0)")
        print("=" * 70)
        print("\nCommands:")
        print("  <your question>    - Ask about the syllabus")
        print("  dept <CODE>        - Switch department (e.g., dept ECE)")
        print("  session            - Show session info")
        print("  quit / exit        - Exit")
        print("=" * 70 + "\n")

        while True:
            try:
                user_input = input("📚 Query> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n👋 Goodbye!\n")
                break

            if not user_input:
                continue

            if user_input.lower() in {'quit', 'exit', 'q'}:
                print("\n👋 Goodbye!\n")
                break

            if user_input.lower() == 'session':
                if self.session_id and self.rag.session_manager:
                    info = self.rag.session_manager.get_session_info(self.session_id)
                    print(f"\n{info}\n")
                else:
                    print("\nNo session manager enabled\n")
                continue

            dept_match = re.match(r'^dept\s+(\S+)$', user_input, re.IGNORECASE)
            if dept_match:
                result = self.rag.set_department(dept_match.group(1), session_id=self.session_id)
                if result["ok"]:
                    print(f"✓ Switched to department {result['department']}\n")
                else:
                    print(f"❌ {result['error']}\n")
                continue

            try:
                result = self.rag.query(
                    user_input,
                    verbose=True,
                    session_id=self.session_id,
                )
                print("─" * 70)
                print("ANSWER:")
                print("─" * 70)
                print(result['answer'])
                print("─" * 70)
                print(
                    f"Method: {result['method']} | "
                    f"Retrieved: {result['chunks_retrieved']} | "
                    f"LLM: {result['llm_used']}"
                )
                print("=" * 70 + "\n")
            except Exception as e:
                print(f"\n❌ Error: {e}\n")


def main():
    from runtime_engine import AcademicRAGSystem

    rag = AcademicRAGSystem(
        department=None,
        persist_path="./vector_db",
        max_context_chars=1500,
        enable_sessions=True,
    )

    interface = InteractiveInterface(rag)
    interface.run()


if __name__ == "__main__":
    main()
