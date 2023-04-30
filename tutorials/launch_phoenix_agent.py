import json
import re
from typing import Optional, Union

import pandas as pd
from langchain.agents import AgentOutputParser, AgentType, Tool, initialize_agent
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts.chat import (
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain.schema import AgentAction, AgentFinish

FORMAT_INSTRUCTIONS = """RESPONSE FORMAT INSTRUCTIONS
----------------------------

When responding to me, please output a response in one of two formats:

**Option 1:**
Use this if you want the human to use a tool.
Markdown code snippet formatted in the following schema:

```json
{{{{
    "action": string, \\ The action to take. Must be one of {tool_names}
    "action_input": "px.Schema(<keyword-arguments>)", \\ The suggested Phoenix schema.
    "message": ""
}}}}
```

**Option #2:**
Use this if you want to respond directly to the human. Markdown code snippet formatted in the following schema:

```json
{{{{
    "action": "Final Answer",
    "message": string \\ The message to send to the human, which will be displayed in the chat.
}}}}
```

The response should start with "```json" and end with "```".
"""


def get_message() -> str:
    return input("Enter a message:\n").strip()


def is_balanced_parentheses(expression: str) -> bool:
    stack = []
    for char in expression:
        if char == "(":
            stack.append(char)
        elif char == ")":
            if not stack:
                return False
            stack.pop()
    return not stack


def parse_phoenix_schema(text: str) -> Optional[str]:
    pattern = r"px\\.Schema\\((.*?)\\)"
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        if is_balanced_parentheses(match):
            return f"px.Schema({match})"
    return None


class PhoenixSchemaAgentOutputParser(AgentOutputParser):
    def get_format_instructions(self) -> str:
        return FORMAT_INSTRUCTIONS

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        cleaned_output = text.strip()
        if cleaned_output.startswith("```json"):
            cleaned_output = cleaned_output[len("```json") :]
        if cleaned_output.endswith("```"):
            cleaned_output = cleaned_output[: -len("```")]
        response = json.loads(cleaned_output)
        action = response["action"]
        action_input = response.get("action_input")
        message = response.get("message")
        if action == "Final Answer":
            return AgentFinish(
                {"output": message},
                text,
            )
        else:
            return AgentAction(action, action_input, text)


example_data_list = [
    {
        "description": "dataframe with timestamp_column_name, prediction_score_column_name, prediction_label_column_name, and actual_label_column_name",
        "dataframe": """pd.DataFrame([
    [pd.to_datetime('2023-03-01 02:02:19'), 0.91, 'click', 'click'],
    [pd.to_datetime('2023-02-17 23:45:48'), 0.37, 'no_click', 'no_click'],
    [pd.to_datetime('2023-01-30 15:30:03'), 0.54, 'click', 'no_click'],
    [pd.to_datetime('2023-02-03 19:56:09'), 0.74, 'click', 'click'],
    [pd.to_datetime('2023-02-24 04:23:43'), 0.37, 'no_click', 'click']
], columns=['timestamp', 'prediction_score', 'prediction', 'target'])""",
        "schema": """px.Schema(
    timestamp_column_name="timestamp",
    prediction_score_column_name="prediction_score",
    prediction_label_column_name="prediction",
    actual_label_column_name="target",
)""",
    },
    {
        "description": "dataframe with prediction_label_column_name, actual_label_column_name, feature_column_names, tag_column_names",
        "dataframe": """pd.DataFrame({
    'fico_score': [578, 507, 656, 414, 512],
    'merchant_id': ['Scammeds', 'Schiller Ltd', 'Kirlin and Sons', 'Scammeds', 'Champlin and Sons'],
    'loan_amount': [4300, 21000, 18000, 18000, 20000],
    'annual_income': [62966, 52335, 94995, 32034, 46005],
    'home_ownership': ['RENT', 'RENT', 'MORTGAGE', 'LEASE', 'OWN'],
    'num_credit_lines': [110, 129, 31, 81, 148],
    'inquests_in_last_6_months': [0, 0, 0, 2, 1],
    'months_since_last_delinquency': [0, 23, 0, 0, 0],
    'age': [25, 78, 54, 34, 49],
    'gender': ['male', 'female', 'female', 'male', 'male'],
    'predicted': ['not_fraud', 'not_fraud', 'uncertain', 'fraud', 'uncertain'],
    'target': ['fraud', 'not_fraud', 'uncertain', 'not_fraud', 'uncertain']
})""",
        "schema": """px.Schema(
    prediction_label_column_name="predicted",
    actual_label_column_name="target",
    feature_column_names=[
        "fico_score",
        "merchant_id",
        "loan_amount",
        "annual_income",
        "home_ownership",
        "num_credit_lines",
        "inquests_in_last_6_months",
        "months_since_last_delinquency",
    ],
    tag_column_names=[
        "age",
        "gender",
    ],
)""",
    },
    {
        "description": "example with prediction_label_column_name, actual_label_column_name, (embedding_feature_column_names with vector_column_name)",
        "dataframe": """pd.DataFrame({
    'predicted': ['fraud', 'fraud', 'not_fraud', 'not_fraud', 'uncertain'],
    'target': ['not_fraud', 'not_fraud', 'not_fraud', 'not_fraud', 'uncertain'],
    'embedding_vector': [[-0.97, 3.98, -0.03, 2.92], [3.20, 3.95, 2.81, -0.09], [-0.49, -0.62, 0.08, 2.03], [1.69, 0.01, -0.76, 3.64], [1.46, 0.69, 3.26, -0.17]],
    'fico_score': [604, 612, 646, 560, 636],
    'merchant_id': ['Leannon Ward', 'Scammeds', 'Leannon Ward', 'Kirlin and Sons', 'Champlin and Sons'],
    'loan_amount': [22000, 7500, 32000, 19000, 10000],
    'annual_income': [100781, 116184, 73666, 38589, 100251],
    'home_ownership': ['RENT', 'MORTGAGE', 'RENT', 'MORTGAGE', 'MORTGAGE'],
    'num_credit_lines': [108, 42, 131, 131, 10],
    'inquests_in_last_6_months': [0, 2, 0, 0, 0],
    'months_since_last_delinquency': [0, 56, 0, 0, 3]
})""",
        "schema": """px.Schema(
    prediction_label_column_name="predicted",
    actual_label_column_name="target",
    embedding_feature_column_names={
        "transaction_embeddings": px.EmbeddingColumnNames(
            vector_column_name="embedding_vector"
        ),
    },
)""",
    },
    #     {
    #         "description": "dataframe with actual_label_column_name, (embedding_feature_column_names with vector_column_name and link_to_data_column_name)",
    #         "dataframe": """pd.DataFrame({
    #     'defective': ['okay', 'defective', 'okay', 'defective', 'okay'],
    #     'image': ['https://www.example.com/image0.jpeg', 'https://www.example.com/image1.jpeg', 'https://www.example.com/image2.jpeg', 'https://www.example.com/image3.jpeg', 'https://www.example.com/image4.jpeg'],
    #     'image_vector': [[1.73, 2.67, 2.91, 1.79, 1.29], [2.18, -0.21, 0.87, 3.84, -0.97], [3.36, -0.62, 2.40, -0.94, 3.69], [2.77, 2.79, 3.36, 0.60, 3.10], [1.79, 2.06, 0.53, 3.58, 0.24]]
    # })""",
    #         "schema": """px.Schema(
    #     actual_label_column_name="defective",
    #     embedding_feature_column_names={
    #         "image_embedding": px.EmbeddingColumnNames(
    #             vector_column_name="image_vector",
    #             link_to_data_column_name="image",
    #         ),
    #     },
    # )""",
    #     },
    #     {
    #         "description": "dataframe with actual_label_column_name, feature_column_names, tag_column_names, (embedding_feature_column_names with vector_column_name and raw_data_column_name)",
    #         "dataframe": """pd.DataFrame({
    #     'defective': ['okay', 'defective', 'okay', 'defective', 'okay'],
    #     'image': ['https://www.example.com/image0.jpeg', 'https://www.example.com/image1.jpeg', 'https://www.example.com/image2.jpeg', 'https://www.example.com/image3.jpeg', 'https://www.example.com/image4.jpeg'],
    #     'image_vector': [[1.73, 2.67, 2.91, 1.79, 1.29], [2.18, -0.21, 0.87, 3.84, -0.97], [3.36, -0.62, 2.40, -0.94, 3.69], [2.77, 2.79, 3.36, 0.60, 3.10], [1.79, 2.06, 0.53, 3.58, 0.24]]
    # })""",
    #         "schema": """px.Schema(
    #     actual_label_column_name="sentiment",
    #     feature_column_names=[
    #         "category",
    #     ],
    #     tag_column_names=[
    #         "name",
    #     ],
    #     embedding_feature_column_names={
    #         "product_review_embeddings": px.EmbeddingColumnNames(
    #             vector_column_name="text_vector",
    #             raw_data_column_name="text",
    #         ),
    #     },
    # )""",
    #     },
]

examples = ""
for example_data in example_data_list:
    examples += f"""Example: {example_data["description"]}
Dataframe:

{example_data["dataframe"]}

Schema:

{example_data["schema"]}
"""
# print(examples)


with open("/Users/xandersong/phoenix/tutorials/api_reference.md") as f:
    api_reference = f.read()


dataframe = pd.read_parquet(
    "https://storage.googleapis.com/arize-assets/phoenix/datasets/unstructured/cv/human-actions/human_actions_training.parquet"
)

sampled_dataframe = dataframe.head(1)
column_to_type = {}
for column in sampled_dataframe.columns:
    column_to_type[column] = repr(type(sampled_dataframe[column].iloc[0]))[
        len("<class '") : -len("'>")
    ]
dataframe_column_to_type = "\n".join(
    [f"{column}: {type_string}" for column, type_string in column_to_type.items()]
)


template = """- You are a helpful chatbot.
- Your goal is to create a Phoenix schema that describes the user's input dataframe.
- You should suggest possible schemas, interact with the user, and ask the user to confirm correctness of the schema.
- You should help the user understand the meaning of each of the fields of phoenix.Schema if they get confused.
- When the user acknowledges that the schema is correct, you should offer to launch Phoenix on their behalf.
- If the user asks you to launch Phoenix, you should call the launch-phoenix tool.

API reference:

{api_reference}

Examples:

{examples}
"""


system_message_prompt_template = SystemMessagePromptTemplate.from_template(template)
system_message = system_message_prompt_template.format(
    api_reference=api_reference,
    examples=examples,
)
# print(system_message.content)


def launch_phoenix(phoenix_schema_expression: str) -> None:
    print("🚀 Launching Phoenix 🔥🐦")
    # phoenix_schema = eval(phoenix_schema_expression)
    # phoenix_dataset = px.Dataset(dataframe, phoenix_schema)
    # px.launch_app(phoenix_dataset)


tools = [
    Tool(
        name="launch-phoenix",
        func=launch_phoenix,
        description="This tool launches the Phoenix app. Do not use this tool without explicit permission from the user.",
    ),
    # Tool(
    #     name="no-op",
    #     func=lambda x: f"No-op {x}",
    #     description="This tool does nothing. You should use this tool if the user has not asked to launch Phoenix.",
    # ),
]


input_message_prompt_template = """Input Dataframe Columns to Data Type:

{dataframe_column_to_type}

Phoenix Schema:
"""

human_message = HumanMessagePromptTemplate.from_template(input_message_prompt_template).format(
    dataframe_column_to_type=dataframe_column_to_type
)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
memory.chat_memory.messages.append(system_message)
memory


model_name = "gpt-3.5-turbo"
llm = ChatOpenAI(model_name=model_name, temperature=0.1)
output_parser = PhoenixSchemaAgentOutputParser()
agent_chain = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
    verbose=True,
    memory=memory,
    agent_kwargs=dict(output_parser=output_parser),
)
message = human_message.content
while True:
    if message is None:
        message = get_message()
    message_to_user = agent_chain.run(
        input=message,
    )
    print(message_to_user)
    message = None
