import json

from langchain_core.prompts import ChatPromptTemplate
from openai import APIError

from app.core.exceptions import QuizGenerationError
from app.llm.langchain_factory import create_chat_model
from app.models.quiz import QuizContent
from app.prompts.quiz_prompt import QUIZ_SYSTEM_PROMPT, QUIZ_USER_PROMPT


def create_quiz_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", QUIZ_SYSTEM_PROMPT),
            ("human", QUIZ_USER_PROMPT),
        ]
    )
    structured_model = create_chat_model(temperature=0.4).with_structured_output(
        QuizContent,
        method="json_mode",
    )
    return prompt | structured_model


class LangChainQuizGenerator:
    def __init__(self, chain=None) -> None:
        self._chain = chain

    async def generate(self, user_input: str) -> QuizContent:
        chain = self._chain if self._chain is not None else create_quiz_chain()
        schema_json = json.dumps(
            QuizContent.model_json_schema(),
            ensure_ascii=False,
        )
        try:
            return await chain.ainvoke(
                {"user_input": user_input, "schema_json": schema_json}
            )
        except APIError as error:
            raise QuizGenerationError() from error
