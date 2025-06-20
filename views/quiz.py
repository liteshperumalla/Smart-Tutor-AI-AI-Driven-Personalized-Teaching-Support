import streamlit as st
import os
import random
import time
import logging
import json
import re
from pathlib import Path
from datetime import datetime
import auth
auth.initialize_session()

from llama_index.core import load_index_from_storage, get_response_synthesizer
from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
from llama_index.core.schema import Document as LlamaDocument

from Tutor_chat import RAGQueryEngine
from utils import get_storage_context, render_footer
from user_management import get_user_dir, save_user_file, load_user_file

@st.cache_data(ttl=600)
def get_knowledge_base_structure():
    storage_context = get_storage_context() 
    if not storage_context:
        st.error("Storage context is not available for loading knowledge base.")
        return {}
    structure = {}
    try:
        index = load_index_from_storage(storage_context)
        docstore = index.docstore
        all_file_paths = [doc.metadata.get("file_path") for doc in docstore.docs.values() if doc.metadata.get("file_path")]
        for file_path_str in all_file_paths:
            p = Path(file_path_str)
            folder = str(p.parent)
            if folder not in structure:
                structure[folder] = []
            structure[folder].append(file_path_str)
        return structure
    except Exception as e:
        st.error(f"Could not load the knowledge base to get folder structure: {e}")
        logging.error(f"Failed to get knowledge base structure: {e}", exc_info=True)
        return {}

def save_quiz_result(user_id, score, total_questions, selected_folders, questions_data):
    """Save quiz result as a unique file in the user's quiz folder."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        quiz_dir = os.path.join(get_user_dir(user_id), "quiz")
        os.makedirs(quiz_dir, exist_ok=True)
        filename = f"quiz_{timestamp}.json"
        result = {
            "timestamp": datetime.now().isoformat(),
            "score": score,
            "total_questions": total_questions,
            "percentage": (score / total_questions * 100) if total_questions > 0 else 0,
            "selected_folders": selected_folders,
            "questions_data": questions_data
        }
        with open(os.path.join(quiz_dir, filename), "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Error saving quiz result for user {user_id}: {e}", exc_info=True)
        return False
def load_all_quiz_results(user_id):
    """Load all quiz results for a user from their quiz folder."""
    quiz_dir = os.path.join(get_user_dir(user_id), "quiz")
    if not os.path.exists(quiz_dir):
        return []
    results = []
    for fname in sorted(os.listdir(quiz_dir), reverse=True):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(quiz_dir, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    results.append(data)
            except Exception as e:
                logging.warning(f"Could not load quiz result {fname}: {e}")
    return results

def render():
    st.title("🧠 Quiz Generator")
    st.markdown("Test your knowledge! Select folders, choose the number of questions, and start your quiz.")

    # Get user ID for file management
    user_id = st.session_state.get("user_name")
    if not user_id:
        st.error("Please login to access the quiz feature.")
        return

    # Load user's quiz history
    quiz_results = load_all_quiz_results(user_id)

    quiz_states = {
        "quiz_questions_list": [], "quiz_options_list": [], "quiz_correct_answers_list": [],
        "quiz_user_answers_list": [], "quiz_feedback_list": [], "quiz_current_q_index": 0,
        "quiz_score": 0, "quiz_started": False, "quiz_completed": False,
        "session_generated_question_texts": set(), "quiz_selected_folders": []
    }
    for key, default_value in quiz_states.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

    # Display quiz history if available
    if quiz_results and not st.session_state.quiz_started:
        with st.expander("📊 Your Quiz History", expanded=False):
            st.write(f"**Total Quizzes Taken:** {len(quiz_results)}")
            recent_results = quiz_results[:5]  # Show last 5 results
            for i, result in enumerate(recent_results):
                timestamp = datetime.fromisoformat(result["timestamp"]).strftime("%Y-%m-%d %H:%M")
                st.write(f"**{timestamp}:** {result['score']}/{result['total_questions']} ({result['percentage']:.1f}%)")
    if not quiz_results:
        st.info("You haven't taken any quizzes yet. Start your first quiz now!")

    if not st.session_state.quiz_started:
        st.subheader("1. Select Folders for Your Quiz")
        kb_structure = get_knowledge_base_structure()
        if not kb_structure:
            st.warning("Could not find any folders. Please check your knowledge base.")
            return

        available_folders = sorted(list(kb_structure.keys()))
        if not available_folders:
            st.warning("No folders available for selection.")
            return

        selected_folders = st.multiselect(
            "Choose one or more folders:",
            options=available_folders,
            default=[available_folders[0]] if available_folders else [],
            key="quiz_folder_select",
            format_func=lambda path: os.path.basename(path) if path and path != '.' else "Root"
        )

        st.subheader("2. Choose Quiz Length")
        num_questions = st.slider("Number of questions:", 1, 10, 5, key="num_quiz_questions_slider")
        st.markdown("---")

        if st.button("🚀 Start Quiz", use_container_width=True, key="start_quiz_main_button"):
            if not selected_folders:
                st.error("Please select at least one folder.")
            else:
                for key in quiz_states:
                    st.session_state[key] = quiz_states[key] 
                st.session_state.session_generated_question_texts = set()
                st.session_state.quiz_selected_folders = selected_folders  # Store selected folders

                with st.spinner(f"Generating {num_questions} unique questions & explanations... This may take a moment."):
                    try:
                        files_for_quiz = [file for folder in selected_folders for file in kb_structure.get(folder, [])]
                        if not files_for_quiz:
                            st.error("Selected folders do not contain any indexed files.")
                            return
                        
                        index = load_index_from_storage(get_storage_context())
                        filters = MetadataFilters(filters=[ExactMatchFilter(key="file_path", value=path) for path in files_for_quiz], condition="or")
                        
                        filtered_retriever = index.as_retriever(filters=filters, similarity_top_k=3) # Context for question & explanation
                        synthesizer = get_response_synthesizer(response_mode="compact")
                        query_engine_quiz = RAGQueryEngine(
                            retriever=filtered_retriever,
                            response_synthesizer=synthesizer,
                            mode="quiz" 
                        )
                        
                        generated_q_count = 0
                        attempts = 0
                        max_attempts_per_question = 5 
                        total_attempts_overall = num_questions * max_attempts_per_question

                        while generated_q_count < num_questions and attempts < total_attempts_overall:
                            attempts += 1
                            llm_response_str = query_engine_quiz.custom_query(
                                "Generate a unique, high-quality multiple-choice question with four options based on the provided context."
                            )
                            
                            try:
                                json_match = re.search(r'\{[\s\S]*\}', llm_response_str)
                                if not json_match:
                                    logging.warning(f"Attempt {attempts}: No JSON found in LLM response: {llm_response_str}")
                                    continue
                                
                                quiz_item_str = json_match.group(0)
                                quiz_item = json.loads(quiz_item_str)

                                if all(k in quiz_item for k in ['question', 'options', 'correct_answer_letter']) and \
                                   isinstance(quiz_item.get('question'), str) and quiz_item['question'].strip() and \
                                   isinstance(quiz_item.get('options'), list) and len(quiz_item['options']) == 4 and \
                                   all(isinstance(opt, str) and opt.strip() for opt in quiz_item['options']) and \
                                   quiz_item.get('correct_answer_letter') in ['A', 'B', 'C', 'D']:
                                    
                                    if quiz_item['question'] not in st.session_state.session_generated_question_texts:
                                        st.session_state.quiz_questions_list.append(quiz_item['question'])
                                        formatted_options = [f"{chr(ord('A') + i)}) {opt}" for i, opt in enumerate(quiz_item['options'])]
                                        st.session_state.quiz_options_list.append(formatted_options)
                                        st.session_state.quiz_correct_answers_list.append(quiz_item['correct_answer_letter'])
                                        
                                        # --- Generate and store dynamic explanation/feedback ---
                                        # The query_engine_quiz uses the filtered_retriever, so context is relevant.
                                        explanation_text = query_engine_quiz.get_related_module(quiz_item['question'])
                                        st.session_state.quiz_feedback_list.append(explanation_text if explanation_text else "No specific explanation generated.")
                                        
                                        st.session_state.session_generated_question_texts.add(quiz_item['question'])
                                        generated_q_count += 1
                                    else:
                                        logging.info(f"Attempt {attempts}: Duplicate question discarded: {quiz_item['question'][:30]}...")
                                else:
                                    logging.warning(f"Attempt {attempts}: Invalid JSON structure: {quiz_item}")
                            except json.JSONDecodeError as e_json:
                                logging.error(f"Attempt {attempts}: JSON parse error: {e_json}\nResponse: {llm_response_str}")
                            except Exception as e_val:
                                 logging.error(f"Attempt {attempts}: Error validating JSON: {e_val}\nItem: {quiz_item if 'quiz_item' in locals() else 'N/A'}")

                        if generated_q_count < num_questions:
                            st.warning(f"Managed to generate {generated_q_count} unique valid questions out of {num_questions} requested. Try selecting more diverse content or fewer questions.")

                        if generated_q_count > 0:
                            st.session_state.quiz_user_answers_list = [None] * generated_q_count
                            st.session_state.quiz_started = True
                            st.rerun()
                        else:
                            st.error("Failed to generate any quiz questions. Please try different selections or check the AI model.")
                            
                    except Exception as e:
                        st.error(f"Error during quiz preparation: {e}")
                        logging.error(f"Quiz prep error: {e}", exc_info=True)

    elif st.session_state.quiz_started and not st.session_state.quiz_completed:
        q_idx = st.session_state.quiz_current_q_index
        total_questions = len(st.session_state.quiz_questions_list)

        if total_questions == 0:
            st.warning("No questions available for this quiz. Please restart.")
            st.session_state.quiz_started = False 
            if st.button("Go Back to Quiz Setup", key="back_to_setup_no_q"): st.rerun()
            return

        if q_idx < total_questions:
            current_question = st.session_state.quiz_questions_list[q_idx]
            current_options_display = st.session_state.quiz_options_list[q_idx] 
            
            st.progress((q_idx + 1) / total_questions, text=f"Question {q_idx + 1} of {total_questions}")
            st.subheader(f"Question {q_idx + 1}")
            st.markdown(f"#### {current_question}")

            with st.form(key=f"quiz_form_q{q_idx}_new"):
                option_labels_for_radio = [opt.split(')', 1)[-1].strip() for opt in current_options_display]
                
                user_selected_option_text = st.radio(
                    "Choose the best answer:", 
                    options=option_labels_for_radio, 
                    key=f"user_answer_q{q_idx}_radio",
                    index=None
                )
                submitted = st.form_submit_button("Submit Answer", use_container_width=True)

                if submitted:
                    if user_selected_option_text is not None:
                        selected_option_index = option_labels_for_radio.index(user_selected_option_text)
                        user_answer_letter = chr(ord('A') + selected_option_index)
                        
                        st.session_state.quiz_user_answers_list[q_idx] = user_answer_letter
                        correct_answer_letter = st.session_state.quiz_correct_answers_list[q_idx]

                        if user_answer_letter == correct_answer_letter:
                            st.session_state.quiz_score += 1
                            st.success("✅ Correct! Great job.")
                        else:
                            st.error(f"❌ Incorrect. The correct answer was: **{correct_answer_letter}**")
                            # The dynamically generated feedback will be shown in the review section.
                            # We could also show it here immediately if desired.
                            # For now, the review section will handle displaying the stored explanation.
                        
                        st.session_state.quiz_current_q_index += 1
                        if st.session_state.quiz_current_q_index >= total_questions:
                            st.session_state.quiz_completed = True
                        time.sleep(1.0 if not st.session_state.quiz_completed else 0.1) # Shorter sleep for better UX
                        st.rerun()
                    else:
                        st.warning("Please select an answer.")
        else:
            st.session_state.quiz_completed = True
            st.rerun()

    if st.session_state.quiz_completed:
        st.balloons()
        st.header("🎉 Quiz Complete! Here's Your Result")
        
        score = st.session_state.quiz_score
        total = len(st.session_state.quiz_questions_list)
        percentage = (score / total) * 100 if total > 0 else 0
        st.metric(label="Your Score", value=f"{score}/{total}", delta=f"{percentage:.1f}%" if total > 0 else "No questions")

        if total == 0: st.warning("No questions were included in this quiz.")
        elif percentage == 100: st.success("Perfect score! 🌟")
        elif percentage >= 70: st.info("Great job! You have a good grasp.")
        else: st.warning("Good effort. Reviewing your answers might help!")

        # Save quiz result using new user file management system
        if total > 0:
            questions_data = []
            for i in range(total):
                if i < len(st.session_state.quiz_questions_list) and \
                   i < len(st.session_state.quiz_user_answers_list) and \
                   i < len(st.session_state.quiz_correct_answers_list) and \
                   i < len(st.session_state.quiz_feedback_list):
                    questions_data.append({
                        "question": st.session_state.quiz_questions_list[i],
                        "user_answer": st.session_state.quiz_user_answers_list[i],
                        "correct_answer": st.session_state.quiz_correct_answers_list[i],
                        "feedback": st.session_state.quiz_feedback_list[i],
                        "options": st.session_state.quiz_options_list[i] if i < len(st.session_state.quiz_options_list) else []
                    })
            
            selected_folders = st.session_state.get("quiz_selected_folders", [])
            save_success = save_quiz_result(user_id, score, total, selected_folders, questions_data)
            
            if not save_success:
                st.warning("Quiz completed but results could not be saved to your profile.")

        if total > 0:
            st.markdown("---")
            st.subheader("Review Your Answers:")
            for i in range(total):
                # Check list bounds
                if i < len(st.session_state.quiz_questions_list) and \
                   i < len(st.session_state.quiz_user_answers_list) and \
                   i < len(st.session_state.quiz_correct_answers_list) and \
                   i < len(st.session_state.quiz_feedback_list):

                    with st.expander(f"Question {i+1}: {st.session_state.quiz_questions_list[i]}", expanded=False):
                        user_ans = st.session_state.quiz_user_answers_list[i]
                        correct_ans = st.session_state.quiz_correct_answers_list[i]
                        
                        st.write(f"**Your Answer:** {user_ans if user_ans else 'Not Answered'}")
                        st.write(f"**Correct Answer:** {correct_ans}")
                        
                        is_correct = (user_ans == correct_ans)
                        
                        if not is_correct:
                            st.markdown(f"<p style='color:red;'>Incorrect.</p>", unsafe_allow_html=True)
                            feedback_info = st.session_state.quiz_feedback_list[i]
                            if feedback_info and feedback_info != "No specific explanation generated.": # Check for meaningful feedback
                                st.info(f"💡 Explanation: {feedback_info}")
                            else:
                                st.info("💡 Tip: Review the relevant material for this question.")
                        else:
                            st.markdown(f"<p style='color:green;'>Correct!</p>", unsafe_allow_html=True)
                else:
                    st.warning(f"Review data missing for Question {i+1}.")
        
        if st.button("🔄 Take Another Quiz", use_container_width=True, key="restart_quiz_final_fresh"):
            for key in quiz_states: 
                st.session_state[key] = quiz_states[key]
            st.session_state.session_generated_question_texts = set()
            st.rerun()

    render_footer()