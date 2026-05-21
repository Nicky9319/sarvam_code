import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI
from test_cases import test_case_1

load_dotenv()

client = OpenAI(
    api_key=os.environ["SARVAM_API_KEY"],
    base_url="https://api.sarvam.ai/v1"
)

system_message = """
    You are Technical assistant having more than 10 years of expereince, 
            you will be given a list of tickets you need to summarize each ticket in one of following categories
            hardware_issue,
            software_issue,
            model_quality,
            billing
            other 

            At the end make sure to generate a one sentence detailed summmary of all the tickets.
            the summary should be crisp but still insightful and should give a clear picture of the overall situation.

            Make sure to give the response in json format as mentioned below
            {
                "ticket_classifications": [
                    {
                        "ticket_id": "12345",
                        "category": "hardware_issue",
                    },
                    {
                        "ticket_id": "12346",
                        "category": "software_issue",
                    }
                ],
                "summary": "Summary of the tickets"
            }


            Examples:
            Input:
            [
                {
                    "ticket_id": "12345",
                    "description": "The device is overheating and shutting down unexpectedly."
                },
                {
                    "ticket_id": "12346",
                    "description": "The software crashes when I try to open it."
                }
            ]

            Output:
            {
                "ticket_classifications": [
                    {
                        "ticket_id": "12345",
                        "category": "hardware_issue",
                    },
                    {
                        "ticket_id": "12346",
                        "category": "software_issue",
                    }
                ],
                "summary": "There are 50 percent tickets related to hardware issues and 50 percent tickets related to software issues. The main hardware issue is overheating and the main software issue is crashing."
            }
    """

response = client.chat.completions.create(
    model="sarvam-m",
    messages=[
        {
            "role": "system",
            "content": system_message
        },
        {
            "role": "user",
            "content": json.dumps(test_case_1["input"])
        }
    ],
    max_tokens=2000
)

raw_output = response.choices[0].message.content


cleaned_output = re.sub(
    r"<think>.*?</think>",
    "",
    raw_output,
    flags=re.DOTALL
).strip()

parsed_json = json.loads(cleaned_output)
print(parsed_json)


for ele in parsed_json["ticket_classifications"]:
    print(f"Ticket ID: {ele['ticket_id']}, Category: {ele['category']}")
    
