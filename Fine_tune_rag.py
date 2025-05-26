import os
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from datasets import load_dataset

# ----------------- SETUP -----------------
# Set Hugging Face token as environment variable or use login()
os.environ["HF_TOKEN"] = "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"

# Device setup
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
torch_dtype = torch.float32  # MPS requires float32

# Model ID
model_id =  "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

# ----------------- LOAD MODEL -----------------
tokenizer = AutoTokenizer.from_pretrained(model_id, use_auth_token=os.environ["HF_TOKEN"])
tokenizer.pad_token = tokenizer.eos_token  # required for llama models

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch_dtype,
    low_cpu_mem_usage=True,
    use_auth_token=os.environ["HF_TOKEN"]
)
model.to(device)

# ----------------- LOAD & FORMAT DATA -----------------
# Replace with your CSV path
dataset = load_dataset("json", data_files={"train": "final_evaluation_1_data.jsonl"})

def format_prompt(example):
    instruction = example["instruction"]
    input_text = example.get("input", "")
    response = example["output"]
    prompt = f"<s>[INST] {instruction.strip()} {input_text.strip()} [/INST] {response.strip()}</s>"
    return {"text": prompt}

dataset = dataset.map(format_prompt)

def tokenize(example):
    return tokenizer(example["text"], padding="max_length", truncation=True, max_length=512)

tokenized_dataset = dataset.map(tokenize, batched=True, remove_columns=dataset["train"].column_names)

# ----------------- TRAINING -----------------
training_args = TrainingArguments(
    output_dir="./llama3-finetuned",
    num_train_epochs=3,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    save_steps=100,
    logging_steps=10,
    save_total_limit=2,
    evaluation_strategy="no",
    fp16=False,
    bf16=False,
    report_to="none"
)

data_collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    tokenizer=tokenizer,
    data_collator=data_collator
)

trainer.train()

# ----------------- SAVE -----------------
trainer.save_model("./llama3-finetuned")
tokenizer.save_pretrained("./llama3-finetuned")
