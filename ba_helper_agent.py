import os
import asyncio
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ModelInfo, ModelFamily
from autogen_agentchat.agents import AssistantAgent, SocietyOfMindAgent
from autogen_agentchat.ui import Console
import aiohttp
from autogen_agentchat.teams import RoundRobinGroupChat


async def get_user_story() -> any:
    api_url = "https://poc-ba-helper-service-3484833342.asia-southeast1.run.app/api/v1/userstory"

    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                return {"error": f"Failed to fetch user story, status code: {response.status}"}
            
async def get_subtask() -> any:
    api_url = "https://poc-ba-helper-service-3484833342.asia-southeast1.run.app/api/v1/subtask"

    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                return {"error": f"Failed to fetch sub-task, status code: {response.status}"}

async def main():
    model_client_ollama = OpenAIChatCompletionClient(
        model="llama3.2:latest",
        base_url=os.environ["OLLAMA_BASE_URL"],
        api_key=os.environ["OPEN_API_KEY"],
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=False,
            family=ModelFamily.UNKNOWN
        )
    )

    user_story_agent = AssistantAgent(
        name="user_story_agent",
        model_client=model_client_ollama,
        system_message="""
        คุณคือ Business Analyst ที่มีความเชี่ยวชาญในการวิเคราะห์ User Story จงนำข้อมูลที่ได้มาสรุป และตอบกลับ
        **หมายเหตุ:**  
            - คุณต้องระบุข้อมูลให้ครบถ้วน แต่ใช้ภาษาที่กระชับ และหลีกเลี่ยงความกำกวม""",
        tools=[get_user_story],
        # reflect_on_tool_use=True
    )

    subtask_agent = AssistantAgent(
        name="subtask_agent",
        model_client=model_client_ollama,
        system_message="""คุณคือ Business Analyst ที่มีความเชี่ยวชาญในการเขียนและวิเคราะห์ Subtask จงนำข้อมูลที่ได้มาสรุป และตอบกลับ
        **หมายเหตุ:**  
            - คุณต้องระบุข้อมูลให้ครบถ้วน แต่ใช้ภาษาที่กระชับ และหลีกเลี่ยงความกำกวม""",
        tools=[get_subtask],
        # reflect_on_tool_use=True
    )

    ba_agent = AssistantAgent(
        name="ba_agent",
        model_client=model_client_ollama,
        system_message="""คุณคือ Business Analyst ที่มีความเชี่ยวชาญในการวิเคราะห์และหาความเชื่อมโยงของ User Story และ Subtask จงนำข้อมูลที่ได้มาตอบคำถาม User ให้ถูกต้องตมข้อมูลที่ได้รับมา และใช้คำที่เข้าใจได้ง่าย
        หน้าที่ของคุณคือ:
        1. นำข้อมูลที่ได้จาก `user_story_agent` มาใช้ในการตอบคำถามเกี่ยวกับ User Story  
        2. นำข้อมูลที่ได้จาก `subtask_agent` มาใช้ในการตอบคำถามเกี่ยวกับ Subtask  
        3. ข้อมูลที่ได้จาก `user_story_agent` และ `subtask_agent` เชื่อมโยงกันด้วย field 'story_id'
        """,
    )

    team = RoundRobinGroupChat(
        participants=[user_story_agent, subtask_agent, ba_agent],
        max_turns=3
    )

    # society_of_mind_agent = SocietyOfMindAgent(
    #     name="society_of_mind",
    #     team=team,
    #     model_client=model_client_ollama,
    #     description="agent ที่ใช้ในการรับข้อมูล User Story และ Sub-Task"
    # )

    # final_team = RoundRobinGroupChat(
    #     participants=[society_of_mind_agent, ba_agent],
    #     max_turns=2,
    # )

    while True:
        user_message = input("User: ")
        if user_message == "exit":
            break

        stream = team.run_stream(task=user_message)
        await Console(stream)

asyncio.run(main())