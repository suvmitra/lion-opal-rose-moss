export const SEED_KNOWLEDGE_BASE = {
  knowledge_base_version: "24.0.17",
  city: "Dublin",
  country: "Ireland",
  postal_code: "D22V048",
  area_code: "D22",
  employment_status: "Employed Full-Time",
  industry: "Information Technology",
  education: "Master's Degree",
  age_range: "40-45",
  has_children: "Yes",
  number_of_children: 1,
  child_gender: "Boy",
  child_age: 8,
  smoking_status: "No, I don't smoke",
  full_name: "Suvabrata Mitra",
  age: 44,
  gender: "Male",
  marital_status: "Married",
  flight_types: "Both domestic and international",
} as const;

export type KnowledgeBase = Record<string, unknown> & {
  household_pets?: string | string[];
  answer_metadata?: Record<string, unknown>;
  personal_question_fallbacks?: Record<string, unknown>;
};
