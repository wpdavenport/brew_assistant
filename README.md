# 🍺 Brew Assistant (Repo-RAG)

**Your AI Head Brewer that actually knows *your* system.**

Welcome to **Brew Assistant**, a repository-based Retrieval Augmented Generation (RAG) system designed to turn your coding assistant into a world-class brewing coach.

## 🚀 Why is this amazing?

Most AI brewing advice is generic. It assumes 5 gallons, 70% efficiency, and tap water.

**Brew Assistant is different.** It consults *this* repository before answering. It knows:
*   **Your Equipment:** It knows your G40's deadspace, your boil-off rates, and your glycol chiller's limits.
*   **Your Water:** It builds recipes from *your* RO baseline, not some generic "city water" profile.
*   **Your History:** It remembers that time you stalled the Belgian Dark Strong and suggests a fix for next time.
*   **Your Doctrine:** It respects your house rules (e.g., "No secondary fermentation," "Closed transfers only").

It's not just a recipe generator; it's a **process engine** focused on repeatability and BJCP competition quality.

## 🛠️ Getting Started

**💡 Pro Tip:** The easiest way to use this is inside **VS Code**. Install your favorite AI chat extension (Gemini, Claude, or ChatGPT), and it will become your personal brewer assistant.

1.  **Clone this Repo**: This is your brewing brain.
2.  Can be used with any AI (Gemini, Claude, or ChatGPT). Put this phrase into ta chat "Beer RAG, read system_prompt.md and become my professional assistant compettion brewer!"
3.  **Fill in your Profiles**:
    *   Edit `profiles/equipment.yaml` with your system stats.
    *   Update `profiles/water_profiles.md` with your source water.
4.  **Activate the Coach**:
    *   Use the `system_prompt.md` to initialize the AI persona.
5.  **Brew**:
    *   *"Design a BJCP 26D Belgian Dark Strong for my system."*
    *   *"Why did my last IPA finish sweet? Check the logs."*
    *   *"Create a fermentation schedule for a German Pilsner."*


## 📂 How it Works

The brain of the operation is the **Knowledge Index**. The AI uses `knowledge_index.md` to navigate your brewing reality.

### The Core Memory
*   **`profiles/equipment.yaml`**: The hard truth about your hardware.
*   **`profiles/water_profiles.md`**: Your water chemistry targets.
*   **`libraries/yeast_library.md`**: Your house strains and how they behave.
*   **`libraries/my_recipes/`**: Your working recipe history and iteration notes.

### The Workflow
1.  **Design**: Ask for a recipe. The AI checks `libraries/beer_research/` and `libraries/bjcp_overlays/` to build a winner.
2.  **Plan**: It generates a minute-by-minute brew day checklist tailored to your system.
3.  **Execute**: It calculates strike temps and salt additions using your specific `tools/calculations.md`.
4.  **Learn**: After the brew, you log the data. The AI uses this to troubleshoot and improve the next batch.

## 🧠 The "Hard Rules"

To keep the AI honest, we enforce these rules:
*   **No Hallucinations**: If a file is missing, the AI must say so.
*   **House First**: We prefer house yeast and processes over generic internet wisdom.
*   **Competition Standard**: Default assumption is "We are brewing to win gold."

---
*Brew better. Brew smarter. Brew with data.* 🍻
