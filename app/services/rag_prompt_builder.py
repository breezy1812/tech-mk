from app.domain.schemas.rag import RetrievedChunk


class RAGPromptBuilder:
    def build_prompt(self, question: str, chunks: list[RetrievedChunk]) -> str:
        context_sections = []
        for chunk in chunks:
            context_sections.append(
                f"[來源: {chunk.file} | chunk: {chunk.chunk}]\n{chunk.content}"
            )

        context = "\n\n".join(context_sections)
        return (
            "你是一個技術知識庫查詢助手。"
            "請只能根據提供的文件內容回答。"
            "如果文件內容不足以回答，請明確說明目前文件中沒有足夠資訊。"
            "不要推測、不要補充文件之外的資訊。"
            "回答後請保持內容精簡且可直接給使用者閱讀。"
            "\n\n"
            f"文件內容:\n{context}\n\n"
            f"使用者問題: {question}"
        )
