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
            return "not have information from excel"

        requirements_list = df.to_dict(orient="records")

        formatted_text = ""
        for i, row in enumerate(requirements_list, start=1):
            formatted_text += f"**Requirement {i}:**\n"
            for key, value in row.items():
                formatted_text += f"   - **{key}**: {value}\n"
            formatted_text += "\n"

        return
    except Exception as e:
        return f"Error Read Excel: {str(e)}"

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
    # model_client = OpenAIChatCompletionClient(
    #     model="llama3.2:latest",
    #     base_url=os.environ["OLLAMA_BASE_URL"],
    #     api_key=os.environ["OPENAI_API_KEY"],
    #     model_info=ModelInfo(
    #         vision=False,
    #         function_calling=True,
    #         json_output=False,
    #         family=ModelFamily.UNKNOWN
    #     )
    # )

    model_client = OpenAIChatCompletionClient(model="gpt-4o-mini")

    model_client_ollama_vision = OpenAIChatCompletionClient(
        model="llama3.2-vision:latest",
        base_url=os.environ["OLLAMA_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
        model_info=ModelInfo(
            vision=True,
            function_calling=True,
            json_output=False,
            family=ModelFamily.UNKNOWN
        )
    )

    requirement_analyze_agent = AssistantAgent(
        name="requirement_analyze_agent",
        model_client=model_client,
        system_message="""คุณคือ Business Analyst ที่มีความเชี่ยวชาญในการวิเคราะห์ Requirement เพื่อสรุปข้อมูลที่สำคัญสำหรับการเขียน User Story  
        หน้าที่ของคุณคือ:
        1. อ่านและทำความเข้าใจ Requirement ที่ได้รับจากไฟล์  
        2. วิเคราะห์และระบุองค์ประกอบที่สำคัญ ได้แก่:
            - วัตถุประสงค์ของ Requirement (Goal)
            - กลุ่มผู้ใช้งานหลัก (Primary Users)
            - ฟังก์ชันการทำงานที่ต้องมี (Core Functionalities)
            - เงื่อนไขหรือข้อกำหนดพิเศษ (Constraints)
        3. จัดทำสรุปในรูปแบบที่กระชับและชัดเจน เพื่อส่งต่อให้ user_story_agent ใช้เป็นข้อมูลตั้งต้นในการเขียน User Story  

        **หมายเหตุ:**  
        - คุณต้องระบุข้อมูลให้ครบถ้วน แต่ใช้ภาษาที่กระชับ และหลีกเลี่ยงความกำกวม  
        - อย่าดัดแปลง Requirement หรือเพิ่มข้อมูลที่ไม่มีใน Requirement เดิม""",
        # tools=[get_requirement_from_excel],
        tools=[get_requirement],
        reflect_on_tool_use=True
    )

    user_story_agent = AssistantAgent(
        name="user_story_agent",
        model_client=model_client,
        system_message="""คุณคือ Business Analyst ที่มีความเชี่ยวชาญในการเขียน User Story  
        หน้าที่ของคุณคือ:
        1. นำข้อมูลที่ได้จาก requirement_analyze_agent มาใช้เป็นแนวทางในการเขียน User Story  
        2. เขียน User Story ตามหลักการ **As a [user role], I want [goal] so that [reason]**  
        3. เพิ่ม **Business Logic**
        4. เพิ่ม **Acceptance Criteria** เพื่อกำหนดเงื่อนไขที่ต้องผ่านในการพัฒนา  
        5. ตรวจสอบว่า User Story มีความสมบูรณ์ และครอบคลุมทุกแง่มุมของ Requirement  

        **โครงสร้างของ User Story:**
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

        **หมายเหตุ:**  
        - เขียนให้อ่านเข้าใจง่าย และสามารถใช้พัฒนาได้จริง  
        - หลีกเลี่ยงการใช้ภาษาที่คลุมเครือ หรือไม่สามารถทดสอบได้
        - อย่าดัดแปลง response ที่ได้ โดย response จะต้องตรงกับโครงสร้างของ User Story ที่กำหนดเท่านั้น""",
        # tools=[get_example_user_story],
        # reflect_on_tool_use=True
    )

    api_agent = AssistantAgent(
        name="api_agent",
        model_client=model_client,
        system_message="""คุณคือระบบที่รับผิดชอบการบันทึก User Story จาก translator_agent ในรูปแบบ string เท่านั้น
        หน้าที่ของคุณคือ:
        1. นำ response ที่ได้จาก translator_agent มาบันทึกไปยัง API โดยไม่ต้องดัดแปลง response ที่ได้รับมา
        2. ตรวจสอบให้แน่ใจว่า User Story ที่บันทึกไปยัง API ไม่มีการดัดแปลงจากที่ได้รับมาจาก translator_agent
        3. เรียก API เพื่อบันทึก User Story
        
        **หมายเหตุ:**
        - ก่อนจบการทำงานจต้องมีการเรียก API ทุกครั้ง""",
        tools=[post_user_story],
    )

    message = MultiModalMessage(
        content=[
            "คุณคือนักวิเคราะห์ UI อธิบายองค์ประกอบของภาพนี้อย่างละเอียดทุก element ที่ปรากฏในรูปภาพและฟังก์ชันที่เกี่ยวข้อง",
            Image.from_file("/Users/a677231/workspace/ba-helper-agent/document/picture/ibank_advance_tranfer_list.png")
        ],
        source="analyze_ui_agent",
    )

    analyze_ui_agent = AssistantAgent(
        name="analyze_ui_agent",
        model_client=model_client,
        system_message="คุณคือ UX/UI Designer อธิบายทุก element ของ UI อย่างละเอียดและฟังก์ชันที่เกี่ยวข้อง",
    )

    translator_agent = AssistantAgent(
        name="translator_agent",
        model_client=model_client,
        system_message="""
        หน้าที่ของคุณคือแปลง User Story ที่ได้รับจาก user_story_agent เป็นภาษาไทย  

        **ข้อกำหนดในการแปล:**  
        1. แปลเนื้อหาให้เป็นภาษาไทยที่อ่านเข้าใจง่ายและเป็นทางการ  
        2. คงไว้ซึ่งคำเฉพาะทางเทคนิค เช่น ชื่อฟังก์ชัน, คำศัพท์เกี่ยวกับซอฟต์แวร์, และคำที่ไม่ควรแปล (เช่น "User Story", "Business Logic", "Acceptance Criteria")  
        3. โครงสร้างของ User Story ต้องคงเดิม และไม่ดัดแปลงเนื้อหาต้นฉบับ  
        4. หลีกเลี่ยงการใช้คำแปลที่อาจทำให้เนื้อหาคลุมเครือหรือเปลี่ยนความหมาย

        **หมายเหตุ:**  
        - หากมีคำเฉพาะที่ไม่แน่ใจว่าควรแปลหรือไม่ ให้คงคำเดิมไว้ในวงเล็บ เช่น "As a System Admin" → "ในฐานะ System Admin (ผู้ดูแลระบบ)"
        """
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

    have_pic = input("คุณมีรูปภาพ User Interface สำหรับ requirement นี้หรือไม่ (Y/n): ")

    if have_pic.lower() == 'y':
        vision_stream = analyze_ui_agent.run_stream(task=message)
        await Console(vision_stream)


    stream = final_team.run_stream(task="เขียน User Story จาก Requirement ที่ได้มา")
    await Console(stream)

    # with open("user_story_agent_team.json", "w") as f:
    #     json.dump(team.dump_component().model_dump(),f,indent=4)

asyncio.run(main())