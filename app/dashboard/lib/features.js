// Feature switches, read at build time.
// The Risk Copilot needs an LLM key on the server (GROQ_API_KEY). Until one is
// set it is hidden from the menu and the tour; the /copilot page still exists
// for direct links and tests. Turn it on with NEXT_PUBLIC_SHOW_COPILOT=1.
export const SHOW_COPILOT = process.env.NEXT_PUBLIC_SHOW_COPILOT === "1";
