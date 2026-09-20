# persona_data.py
# Data version is kept inside the stable filename.

PERSONA_VERSION = "24.0.7"

MASTER_USER_PERSONA = {
    "demographics": {
        "full_name": "Suvabrata Mitra",
        "age": 44,
        "gender": "Male",
        "marital_status": "Married",
        "dependents": "1 child (Boy, ~8 years old)",
        "current_location": "Dublin, Ireland",
        "citizenship_nationality": "Indian / Resident in Ireland"
    },
    "education": {
        "highest_degree": "Postgraduate / Master's Degree",
        "degrees": [
            {
                "degree": "AIML Data Science",
                "institution": "IIIT Hyderabad",
                "year": 2018
            },
            {
                "degree": "MBA in Supply Chain – International Business",
                "institution": "ICFAI University",
                "year": 2017
            },
            {
                "degree": "Information Systems Management (GNIIT)",
                "institution": "NIIT",
                "year": 2007
            },
            {
                "degree": "Bachelor of Commerce (B.Com)",
                "institution": "Calcutta University",
                "year": 2003
            }
        ],
        "field_of_study": "Computer Science / Data Science / Business Administration"
    },
    "professional_profile": {
        "current_title": "Lead Data Scientist / Senior Manager",
        "industry": "Information Technology / Life Sciences & Pharmaceuticals",
        "company": "Cognizant Technology Solutions",
        "total_experience_years": "19+ years",
        "seniority_level": "Senior Lead / Management / Executive",
        "company_size": "10,000+ employees",
        "domain_expertise": [
            "Life Sciences R&D",
            "Clinical Trials Operations & Analytics",
            "Pharma Supply Chain",
            "Generative AI & Agentic AI Architectures"
        ]
    },
    "technical_skills": {
        "primary_languages": ["Python", "SQL", "PL/SQL", "C#", "VBA"],
        "ai_ml_frameworks": ["TensorFlow", "Keras", "LangChain", "AutoGen", "Transformers", "PyTorch"],
        "cloud_and_infrastructure": ["AWS", "Azure", "Docker", "SaladCloud", "Nvidia GPUs"],
        "databases": ["Chroma DB", "FAISS", "SQL Server"]
    },
    "household_and_lifestyle": {
        "employment_status": "Employed Full-Time",
        "housing": "Renting Apartment (Dublin)",
        "tech_adoption": "Early Adopter / Tech Enthusiast",
        "primary_transport": "Public Transit / Commuter"
    },
    "travel_and_mobility": {
        "flight_types": "Both domestic and international",
        "flight_types_provenance": "Inferred with explicit user authorization",
        "flight_types_confidence": 0.72,
        "inference_basis": [
            "Resident in Ireland with Indian nationality/background",
            "International professional context across Switzerland, the UK and the USA",
            "User authorized a reasonable fallback answer for ordinary personal questions"
        ],
        "global_professional_regions": ["Ireland", "India", "Switzerland", "United Kingdom", "United States"]
    },
    "profile_sources": {
        "linkedin": "https://www.linkedin.com/in/suvabratalive/",
        "github": "https://github.com/mitrasuvabrata-eng",
        "resume": "Suvabrata Mitra_AIML Lead Data Scientist.pdf",
        "source_note": "LinkedIn URL is user-provided. Use only locally supplied or verified profile facts; do not invent inaccessible page content."
    },
    "answer_policy": {
        "allow_reasonable_personal_inference": True,
        "persist_inferred_answers_for_consistency": True,
        "prefer_substantive_answer_over_escape_link": True,
        "label_inferred_answers": True,
        "do_not_infer_sensitive_medical_legal_financial_or_security_facts": True
    }
}