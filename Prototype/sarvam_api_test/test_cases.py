
test_case_1 = {
    "input": 
        [
    {
        "ticket_id": "20001",
        "description": "The laptop battery drains from 100% to 20% within 30 minutes even when idle."
    },
    {
        "ticket_id": "20002",
        "description": "Application freezes every time I upload a CSV larger than 50MB."
    },
    {
        "ticket_id": "20003",
        "description": "The AI model keeps generating irrelevant responses for finance-related prompts."
    },
    {
        "ticket_id": "20004",
        "description": "I was charged twice for the enterprise subscription renewal this month."
    },
    {
        "ticket_id": "20005",
        "description": "Need help understanding how to configure SSO for our organization."
    }
]
    ,

    "output": {
        
    "ticket_classifications": [
        {
            "ticket_id": "20001",
            "category": "hardware_issue",
        },
        {
            "ticket_id": "20002",
            "category": "software_issue",
        },
        {
            "ticket_id": "20003",
            "category": "model_quality",
        },
        {
            "ticket_id": "20004",
            "category": "billing",
        },
        {
            "ticket_id": "20005",
            "category": "other",
        }
    ],
    "summary": "20 percent of tickets relate to hardware problems, 20 percent to software failures, 20 percent to model quality concerns, 20 percent to billing issues, and 20 percent to general support requests. Common issues include battery drain, application freezing, incorrect AI responses, duplicate billing, and SSO configuration assistance."

    }
}



test_case_2 = {
    "input": 
        [
    {
        "ticket_id": "30001",
        "description": "GPU temperature reaches 95 degrees Celsius during rendering tasks."
    },
    {
        "ticket_id": "30002",
        "description": "Keyboard keys are not responding intermittently."
    },
    {
        "ticket_id": "30003",
        "description": "The desktop client crashes immediately after login."
    },
    {
        "ticket_id": "30004",
        "description": "Invoices are missing from the billing dashboard."
    },
    {
        "ticket_id": "30005",
        "description": "The chatbot hallucinates product specifications that do not exist."
    },
    {
        "ticket_id": "30006",
        "description": "Unable to reset password because reset email never arrives."
    }
]
    ,

    "output": {
        
    "ticket_classifications": [
        {
            "ticket_id": "30001",
            "category": "hardware_issue",
        },
        {
            "ticket_id": "30002",
            "category": "hardware_issue",
        },
        {
            "ticket_id": "30003",
            "category": "software_issue",
        },
        {
            "ticket_id": "30004",
            "category": "billing",
        },
        {
            "ticket_id": "30005",
            "category": "model_quality",
        },
        {
            "ticket_id": "30006",
            "category": "software_issue",
        }
    ],
    "summary": "Hardware issues account for 33 percent of tickets, software issues for 33 percent, billing problems for 17 percent, and model quality concerns for 17 percent. Frequent complaints include overheating GPUs, crashing applications, email delivery failures, and inaccurate AI-generated responses."

    }
}
 