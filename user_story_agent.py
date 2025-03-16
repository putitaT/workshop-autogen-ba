import os
import asyncio
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ModelInfo, ModelFamily, SystemMessage, UserMessage, AssistantMessage
from autogen_agentchat.agents import AssistantAgent, SocietyOfMindAgent
from autogen_agentchat.ui import Console
import aiohttp
from pathlib import Path
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination, TokenUsageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
import re
import pandas as pd
from autogen_core import Image
from autogen_agentchat.messages import MultiModalMessage
import json

async def get_requirement() -> any:
    return Path("./document/req4.txt").read_text(encoding="utf-8")

async def get_requirement_from_excel() -> str:
    file_path = "./document/Requirement_ibank_Phase3.xlsx"
    sheet_name = "Product Condition Business"
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")

        if df.empty:
            return []

        requirements_list = df.to_dict(orient="records")

        return requirements_list
    
    except Exception as e:
        return f"Error reading Excel: {str(e)}"

# async def get_example_user_story() -> any:
#     return Path("./document/example_user_story.txt").read_text(encoding="utf-8")

async def post_user_story(user_story: str, story_name: str) -> str:
    api_url = "https://poc-ba-helper-service-3484833342.asia-southeast1.run.app/api/v1/userstory/create"
    payload = {
        "title": story_name,
        "description": user_story,
        "priority": "Medium",
        "status": "To Do"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(api_url, json=payload) as response:
            if response.status == 200:
                return "✅ User Story ถูกบันทึกเรียบร้อยแล้ว!"
            else:
                return f"❌ ไม่สามารถบันทึก User Story ได้: {await response.text()}"

async def main():
    model_client = OpenAIChatCompletionClient(model="gpt-4o-mini")

    requirement_analyze_agent = AssistantAgent(
        name="requirement_analyze_agent",
        model_client=model_client,
        system_message="""
        You are a Business Analyst specializing in requirement analysis to extract key information for writing User Stories. 
        Your responsibilities include:
        1. Reading and understanding the given requirements from a file.
        2. Analyzing and identifying essential components, such as:
            - Objective of the requirement (Goal)
            - Primary user group
            - Core functionalities needed
            - Constraints or special conditions
        3. Summarizing the information concisely and clearly to provide input for the `user_story_agent` in writing the User Story.
        
        **Notes:**
        - Provide complete information while keeping it concise and avoiding ambiguity.
        - Do not modify the original requirements or add non-existent information.
        """,
        tools=[get_requirement_from_excel],
        # reflect_on_tool_use=True
    )

    user_story_agent = AssistantAgent(
        name="user_story_agent",
        model_client=model_client,
        system_message="""
        You are a Business Analyst specializing in writing User Stories.
        Your responsibilities include:
        1. Utilizing the information from `requirement_analyze_agent` as a guideline for writing the User Story.
        2. Writing User Stories following the structure: **As a [user role], I want [goal] so that [reason].**
        3. Adding **Business Logic**.
        4. Adding **Acceptance Criteria** to define conditions for development validation.
        5. Ensuring that the User Story is complete and covers all aspects of the requirement.
        
        **User Story Structure:**
            ### STORY NAME: [story_name]
            #### AS A  
            [user role] 
            #### I WANT TO  
            [goal] 
            #### SO THAT  
            [reason]

            **Business Logic:**  
            - [BUSINESS_LOGIC]

            **Acceptance Criteria:**  
            - [ ] [LIST_ACCEPT_CRITERIA]  
        ***************************
        
        **Notes:**
        - Write in a way that is easy to understand and implement.
        - Avoid vague or untestable language.
        - Do not modify the response structure, ensuring it adheres exactly to the required format.
        """
    )

    # message = MultiModalMessage(
    #     content=[
    #         "You are a UI analyst. Explain every element in this image in detail, including all visible components and related functions.",
    #         Image.from_file("/Users/a677231/workspace/ba-helper-agent/document/picture/ibank_advance_tranfer_list.png")
    #     ],
    #     source="analyze_ui_agent",
    # )

    # analyze_ui_agent = AssistantAgent(
    #     name="analyze_ui_agent",
    #     model_client=model_client,
    #     system_message="You are a UX/UI Designer. Provide a detailed explanation of every UI element and related functions. ***RESPONSE IN THAI ONLY***"
    # )

    translator_agent = AssistantAgent(
        name="translator_agent",
        model_client=model_client,
        system_message="""
        Your responsibility is to translate the User Story received from `user_story_agent` into Thai.
        
        **Translation Guidelines:**
        1. Translate the content into formal and easy-to-read Thai.
        2. No need to translate specific words and technical terms such as function names, story name, software-related terminology, and words that should not be translated 
        (e.g., "User Story", "Business Logic", "Acceptance Criteria", "User Name", "AS A", "I WANT TO", "SO THAT") **USE ENGLISH AS USUAL**.
        3. Maintain the structure of the User Story and do not alter the original content.
        4. Avoid translations that could introduce ambiguity or change the meaning.
        
        **Notes:**
        - If unsure whether a term should be translated, retain the original term in parentheses.
        """
    )

    api_agent = AssistantAgent(
        name="api_agent",
        model_client=model_client,
        system_message="""
        You are responsible for saving the User Story from `translator_agent` in string format only.
        Your tasks include:
        1. Receiving the response from `translator_agent` and storing it in an API without modifying it.
        2. Ensuring that the User Story saved in the API matches exactly what was received from `translator_agent`.
        3. Calling the API to save the User Story.
        
        **Note:**
        - The API call must be made at the end of the process.
        """,
        tools=[post_user_story],
    )

    # termination_condition = MaxMessageTermination(4) | TextMentionTermination("✅ User Story ถูกบันทึกเรียบร้อยแล้ว!") 
    # termination_condition = TextMentionTermination("SUCCESS") 
    team = RoundRobinGroupChat(
        participants=[requirement_analyze_agent, user_story_agent],
        max_turns=2
    )

    society_of_mind_agent = SocietyOfMindAgent(
        name="society_of_mind_agent",
        team=team,
        model_client=model_client
    )

    final_team = RoundRobinGroupChat(
        participants=[society_of_mind_agent, translator_agent, api_agent],
        max_turns=3,
    )

    # have_pic = input("คุณมีรูปภาพ User Interface สำหรับ requirement นี้หรือไม่ (Y/n): ")

    # if have_pic.lower() == 'y':
    #     vision_stream = analyze_ui_agent.run_stream(task=message)
    #     await Console(vision_stream)


    stream = final_team.run_stream(task="Write User Story from recieve requirement")
    await Console(stream)

    # with open("user_story_agent_team.json", "w") as f:
    #     json.dump(team.dump_component().model_dump(),f,indent=4)

asyncio.run(main())
