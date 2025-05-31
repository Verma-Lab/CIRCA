#         flow_instruction_context = f"""
# Current Flow Instructions:

# • **Menu-Items**  
#   “What are you looking for today?  
#    1. Pregnancy test  
#    2. Early pregnancy-loss support  
#    3. Abortion  
#    4. Symptoms-related help  
#    5. Miscarriage support”

# • **Pregnancy-Test**  
#   “Have you had a positive pregnancy test? Reply yes, no, or unsure.”

# • **LMP-Query**  
#   “Do you know the day of your last menstrual period?”

# • **LMP-Date**  
#   “What was the first day of your last menstrual period? (MM/DD/YYYY)”

# • **Symptom-Triage**  
#   “What symptom are you experiencing? Reply ‘Bleeding’, ‘Nausea’, or ‘Vomiting’.”

# –– **Bleeding branch** ––  
# • **Bleeding-Triage**  
#   “Have you had a history of ectopic pregnancy? Reply EY for Yes, EN for No.”

# • **Bleeding-Heavy-Check**  
#   “Is the bleeding heavy (4+ super-pads in 2 hrs)? Reply Y or N.”

# • **Bleeding-Urgent**  
#   “This could be serious. Please call your OB/GYN at [clinic_phone] or go to ER. Are you seeing miscarriage?”

# • **Bleeding-Pain-Check**  
#   “Are you experiencing any pain or cramping? Reply Y or N.”

# • **Bleeding-Advice**  
#   “Please monitor your bleeding and note the color. Contact your provider. I’ll check in in 24 hrs.”

# –– **Nausea branch** ––  
# • **Nausea-Triage**  
#   “Have you been able to keep food or liquids down in the last 24 hrs? Reply Y or N.”

# • **Nausea-Advice**  
#   “Try small meals, ginger, or vitamin B6. I’ll check back in 24 hrs.”

# • **Nausea-Urgent**  
#   “If you can’t keep anything down, contact your provider or PEACE at [clinic_phone]. You might need Unisom.”

# –– **Miscarriage support** ––  
# • **Miscarriage-Support**  
#   “I’m sorry you’re going through this. Do you need emotional support or infection-prevention support?”

# • **Miscarriage-Emotions**  
#   “How are you feeling emotionally? I can connect you to social resources if needed.”

# • **Miscarriage-Infection**  
#   “To prevent infection, avoid tampons, sex, or swimming. Let me know if you develop fever.”

# • **Call-Transfer**  
#   “I’m transferring you now to a specialist for further assistance.”  

# """

#         flow_instruction_context = f"""
#         Main Patient Journey Flows

#         Main Patient Journey Flows

#         • **Start Conversation** (current_node_id: start_conversation)
#           "Hi $patient_firstname! I'm here to help you with your healthcare needs. What would you like to talk about today? A) I have a question about symptoms B) I have a question about medications C) I have a question about an appointment D) Information about what to expect at a PEACE visit E) I have a question about a pregnancy test  F) I need help with pregnancy loss  G) Something else H) Nothing at this time Reply with just one letter."
#           (next_node_id: menu_items)

# • **Menu-Items** (current_node_id: menu_items)
#   "What are you looking for today? A) I have a question about symptoms B) I have a question about medications C) I have a question about an appointment D) Information about what to expect at a PEACE visit E) I have a question about a pregnancy test F) I need help with pregnancy loss G) Something else H) Nothing at this time I) Take the Pre-Program Impact Survey J) Take the Post-Program Impact Survey K) Take the NPS Quantitative Survey Reply with just one letter."
#   –– If A (Symptoms) –– (next_node_id: symptoms_response)
#   –– If B (Medications) –– (next_node_id: medications_response)
#   –– If C (Appointment) –– (next_node_id: appointment_response)
#   –– If D (PEACE Visit) –– (next_node_id: peace_visit_response_part_1)
#   –– If E (Pregnancy Test) –– (next_node_id: follow_up_confirmation_of_pregnancy_survey)
#   –– If F (Pregnancy Loss) –– (next_node_id: pregnancy_loss_response)
#   –– If G (Something Else) –– (next_node_id: something_else_response)
#   –– If H (Nothing) –– (next_node_id: nothing_response)
#   –– If I (Pre-Program Impact Survey) –– (next_node_id: pre_program_impact_survey)
#   –– If J (Post-Program Impact Survey) –– (next_node_id: post_program_impact_survey)
#   –– If K (NPS Quantitative Survey) –– (next_node_id: nps_quantitative_survey)

#         • **Onboarding** (current_node_id: onboarding)
#           "Initial patient enrollment with four main branches: Pregnancy Preference Unknown, Desired Pregnancy Preference, Undesired/Unsure Pregnancy Preference, Early Pregnancy Loss. Final pathways to either Offboarding or Program Archived."
#           (next_node_id: follow_up_confirmation_of_pregnancy_survey)

#         • **Follow-Up Confirmation of Pregnancy Survey** (current_node_id: follow_up_confirmation_of_pregnancy_survey)
#           "Hi $patient_firstname. As your virtual health buddy, my mission is to help you find the best care for your needs. Have you had a moment to take your home pregnancy test? Reply Y or N"
#           (next_node_id: pregnancy_test_results_nlp_survey)
# (next_node_id: pregnancy_test_results_nlp_survey)

# • Pregnancy Test Results NLP Survey (current_node_id: pregnancy_test_results_nlp_survey)

# "It sounds like you're sharing your pregnancy test results, is that correct? Reply Y or N"

# –– If N (Pregnancy Test Results) –– (next_node_id: default_response)

# –– If Y (Pregnancy Test Results) –– (next_node_id: pregnancy_test_result_confirmation)

# • Default Response (current_node_id: default_response)

# "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

# (next_node_id: null)

# • Pregnancy Test Result Confirmation (current_node_id: pregnancy_test_result_confirmation)

# "Were the results positive? Reply Y or N"

# –– If YES (Result Positive) –– (next_node_id: ask_for_lmp)

# –– If NO (Result Negative) –– (next_node_id: negative_test_result_response)

# • Ask for LMP (current_node_id: ask_for_lmp)

# "Sounds good. In order to give you accurate information, it's helpful for me to know the first day of your last menstrual period (LMP). Do you know this date? Reply Y or N (It's OK if you're uncertain)"

# –– If Y (LMP Known) –– (next_node_id: enter_lmp_date)

# –– If N (LMP Unknown) –– (next_node_id: ask_for_edd)

# • Enter LMP Date (current_node_id: enter_lmp_date)

# "Great. Your LMP is a good way to tell your gestational age. Please reply in this format: MM/DD/YYYY"

# (next_node_id: lmp_date_received)

# • LMP Date Received (current_node_id: lmp_date_received)

# "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps. Stay tuned for your estimated gestational age, we're calculating it now."

# (next_node_id: pregnancy_intention_survey)

# • Ask for EDD (current_node_id: ask_for_edd)

# "Not a problem. Do you know your Estimated Due Date? Reply Y or N (again, it's OK if you're uncertain)"

# –– If Y (EDD Known) –– (next_node_id: enter_edd_date)

# –– If N (EDD Unknown) –– (next_node_id: check_penn_medicine_system)

# • Enter EDD Date (current_node_id: enter_edd_date)

# "Great. Please reply in this format: MM/DD/YYYY"

# (next_node_id: edd_date_received)

# • EDD Date Received (current_node_id: edd_date_received)

# "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps. Stay tuned for your estimated gestational age, we're calculating it now."

# (next_node_id: pregnancy_intention_survey)

# • Check Penn Medicine System (current_node_id: check_penn_medicine_system)

# "We know it can be hard to keep track of periods sometimes. Have you been seen in the Penn Medicine system? Reply Y or N"

# –– If Y (Seen in Penn System) –– (next_node_id: penn_system_confirmation)

# –– If N (Not Seen in Penn System) –– (next_node_id: register_as_new_patient)

# • Penn System Confirmation (current_node_id: penn_system_confirmation)

# "Perfect. Over the next few days we're here for you and ready to help with your next moves. Stay tuned!"

# (next_node_id: pregnancy_intention_survey)

# • Register as New Patient (current_node_id: register_as_new_patient)

# "Not a problem. Contact the call center $clinic_phone$ and have them add you as a 'new patient'. This way, if you need any assistance in the future, we'll be able to help you quickly."

# (next_node_id: pregnancy_intention_survey)

# • Negative Test Result Response (current_node_id: negative_test_result_response)

# "Thanks for sharing. If you have any questions or if there's anything you'd like to talk about, we're here for you. Contact the call center $clinic_phone$ for any follow-ups & to make an appointment with your OB/GYN."

# (next_node_id: offboarding_after_negative_result)

# • Offboarding After Negative Result (current_node_id: offboarding_after_negative_result)

# "Being a part of your care journey has been a real privilege. Since I only guide you through this brief period, I won't be available for texting after today. If you find yourself pregnant in the future, text me back at this number, and I'll be here to support you once again."

# (next_node_id: null)

# • Pregnancy Intention Survey (current_node_id: pregnancy_intention_survey)

# "$patient_firstName$, pregnancy can stir up many different emotions. These can range from uncertainty and regret to joy and happiness. You might even feel multiple emotions at the same time. It's okay to have these feelings. We're here to help support you through it all. I'm checking in on how you're feeling about being pregnant. Are you: A) Excited B) Not sure C) Not excited Reply with just 1 letter"

# –– If A (Excited) –– (next_node_id: excited_response)

# –– If B (Not Sure) –– (next_node_id: not_sure_response)

# –– If C (Not Excited) –– (next_node_id: not_excited_response)

# • Excited Response (current_node_id: excited_response)

# "Well that is exciting news! Some people feel excited, and want to continue their pregnancy, and others aren't sure. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you."

# (next_node_id: care_options_prompt)

# • Not Sure Response (current_node_id: not_sure_response)

# "We're here to support you. Some people feel excitement, and want to continue their pregnancy, and others aren't sure or want an abortion. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you."

# (next_node_id: care_options_prompt)

# • Not Excited Response (current_node_id: not_excited_response)

# "We're here to support you. Some people feel excitement, and want to continue their pregnancy, and others aren't sure or want an abortion. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you."

# (next_node_id: care_options_prompt)

# • Care Options Prompt (current_node_id: care_options_prompt)

# "Would you prefer us to connect you with providers who can help with: A) Continuing my pregnancy B) Talking with me about what my options are C) Getting an abortion Reply with just 1 letter"

# –– If A (Continuing Pregnancy) –– (next_node_id: prenatal_provider_check)

# –– If B (Options) –– (next_node_id: connect_to_peace_clinic)

# –– If C (Abortion) –– (next_node_id: connect_to_peace_for_abortion)

# • Prenatal Provider Check (current_node_id: prenatal_provider_check)

# "Do you have a prenatal provider? Reply Y or N"

# –– If Y (Has Prenatal Provider) –– (next_node_id: schedule_appointment)

# –– If N (No Prenatal Provider) –– (next_node_id: schedule_with_penn_obgyn)

# • Schedule Appointment (current_node_id: schedule_appointment)

# "Great, it sounds like you're on the right track! Call $clinic_phone$ to make an appointment."

# (next_node_id: null)

# • Schedule with Penn OB/GYN (current_node_id: schedule_with_penn_obgyn)

# "It's important to receive prenatal care early on. Sometimes it takes a few weeks to get in. Call $clinic_phone$ to schedule an appointment with Penn OB/GYN Associates or Dickens Clinic."

# (next_node_id: null)

# • Connect to PEACE Clinic (current_node_id: connect_to_peace_clinic)

# "We understand your emotions, and it's important to take the necessary time to navigate through them. The team at The Pregnancy Early Access Center (PEACE) provides abortion, miscarriage management, and pregnancy prevention. Call $clinic_phone$ to schedule an appointment with PEACE. https://www.pennmedicine.org/make-an-appointment"

# (next_node_id: null)

# • Connect to PEACE for Abortion (current_node_id: connect_to_peace_for_abortion)

# "Call $clinic_phone$ to be scheduled with PEACE. https://www.pennmedicine.org/make-an-appointment We'll check back with you to make sure you're connected to care. We have a few more questions before your visit. It'll help us find the right care for you."

# (next_node_id: null)

# Symptom Management Flows

# • Menu-Items (current_node_id: menu_items)

# "What are you looking for today? A) I have a question about symptoms B) I have a question about medications C) I have a question about an appointment D) Information about what to expect at a PEACE visit E) Something else F) Nothing at this time Reply with just one letter."

# –– If A (Symptoms) –– (next_node_id: symptoms_response)

# –– If B (Medications) –– (next_node_id: medications_response)

# –– If C (Appointment) –– (next_node_id: appointment_response)

# –– If D (PEACE Visit) –– (next_node_id: peace_visit_response_part_1)

# –– If E (Something Else) –– (next_node_id: something_else_response)

# –– If F (Nothing) –– (next_node_id: nothing_response)

# • Symptoms Response (current_node_id: symptoms_response)

# "We understand questions and concerns come up. You can try texting this number with your question, and I may have an answer. This isn't an emergency line, so it’s best to reach out to your provider if you have an urgent concern by calling $clinic_phone$. If you're worried or feel like this is something serious – it's essential to seek medical attention."

# (next_node_id: symptom_triage)

# • Medications Response (current_node_id: medications_response)

# "Each person — and every medication — is unique, and not all medications are safe to take during pregnancy. Make sure you share what medication you're currently taking with your provider. Your care team will find the best treatment option for you. List of safe meds: https://hspogmembership.org/stages/safe-medications-in-pregnancy"

# (next_node_id: null)

# • Appointment Response (current_node_id: appointment_response)

# "Unfortunately, I can’t see when your appointment is, but you can call the clinic to find out more information. If I don’t answer all of your questions, or you have a more complex question, you can contact the Penn care team at $clinic_phone$ who can give you further instructions. I can also provide some general information about what to expect at a visit. Just ask me."

# (next_node_id: null)

# • PEACE Visit Response Part 1 (current_node_id: peace_visit_response_part_1)

# "The Pregnancy Early Access Center is a support team who's here to help you think through the next steps and make sure you have all the information you need. They're a listening ear, judgment-free and will support any decision you make. You can have an abortion, you can place the baby for adoption or you can continue the pregnancy and choose to parent. They are there to listen to you and answer any of your questions."

# (next_node_id: peace_visit_response_part_2)

# • PEACE Visit Response Part 2 (current_node_id: peace_visit_response_part_2)

# "Sometimes, they use an ultrasound to confirm how far along you are to help in discussing options for your pregnancy. If you're considering an abortion, they'll review both types of abortion (medical and surgical) and tell you about the required counseling and consent (must be done at least 24 hours before the procedure). They can also discuss financial assistance and connect you with resources to help cover the cost of care."

# (next_node_id: null)

# • Something Else Response (current_node_id: something_else_response)

# "OK, I understand and I might be able to help. Try texting your question to this number. Remember, I do best with short sentences about one topic. If you need more urgent help or prefer to speak to someone on the phone, you can reach your care team at $clinic_phone$ & ask for your clinic. If you're worried or feel like this is something serious – it's essential to seek medical attention."

# (next_node_id: null)

# • Nothing Response (current_node_id: nothing_response)

# "OK, remember you can text this number at any time with questions or concerns."

# (next_node_id: null)

# • Symptom-Triage (current_node_id: symptom_triage)

# "What symptom are you experiencing? Reply 'Bleeding', 'Nausea', 'Vomiting', 'Pain', or 'Other'"

# –– If Bleeding –– (next_node_id: vaginal_bleeding_1st_trimester)

# –– If Nausea –– (next_node_id: nausea_1st_trimester)

# –– If Vomiting –– (next_node_id: vomiting_1st_trimester)

# –– If Pain –– (next_node_id: pain_early_pregnancy)

# –– If Other –– (next_node_id: default_response)

# • Vaginal Bleeding - 1st Trimester (current_node_id: vaginal_bleeding_1st_trimester)

# "Let me ask a few more questions about your medical history to determine the next best steps. Have you ever had an ectopic pregnancy (this is a pregnancy in your tube or anywhere outside of your uterus)? Reply Y or N"

# –– If Y (Previous Ectopic Pregnancy) –– (next_node_id: immediate_provider_visit)

# –– If N (No Previous Ectopic Pregnancy) –– (next_node_id: heavy_bleeding_check)

# • Immediate Provider Visit (current_node_id: immediate_provider_visit)

# "Considering your past history, you should be seen by a provider immediately. Now: Call your OB/GYN ASAP (Call $clinic_phone$ to make an urgent appointment with PEACE – the Early Pregnancy Access Center – if you do not have a provider) If you're not feeling well or have a medical emergency, visit your local ER."

# (next_node_id: null)

# • Heavy Bleeding Check (current_node_id: heavy_bleeding_check)

# "Over the past 2 hours, is your bleeding so heavy that you've filled 4 or more super pads? Reply Y or N"

# –– If Y (Heavy Bleeding) –– (next_node_id: urgent_provider_visit_for_heavy_bleeding)

# –– If N (No Heavy Bleeding) –– (next_node_id: pain_or_cramping_check)

# • Urgent Provider Visit for Heavy Bleeding (current_node_id: urgent_provider_visit_for_heavy_bleeding)

# "This amount of bleeding during pregnancy means you should be seen by a provider immediately. Now: Call your OB/GYN. (Call $clinic_phone$, option 5 to make an urgent appointment with PEACE – the Early Pregnancy Access Center) If you're not feeling well or have a medical emergency, visit your local ER."

# (next_node_id: null)

# • Pain or Cramping Check (current_node_id: pain_or_cramping_check)

# "Are you in any pain or cramping? Reply Y or N"

# –– If Y (Pain or Cramping) –– (next_node_id: er_visit_check_during_pregnancy)

# –– If N (No Pain or Cramping) –– (next_node_id: monitor_bleeding)

# • ER Visit Check During Pregnancy (current_node_id: er_visit_check_during_pregnancy)

# "Have you been to the ER during this pregnancy? Reply Y or N"

# –– If Y (Been to ER) –– (next_node_id: report_bleeding_to_provider)

# –– If N (Not Been to ER) –– (next_node_id: monitor_bleeding_at_home)

# • Report Bleeding to Provider (current_node_id: report_bleeding_to_provider)

# "Any amount of bleeding during pregnancy should be reported to a provider. Call your provider for guidance."

# (next_node_id: continued_bleeding_follow_up)

# • Monitor Bleeding at Home (current_node_id: monitor_bleeding_at_home)

# "While bleeding or spotting in early pregnancy can be alarming, it's pretty common. Based on your exam in the ER, it's okay to keep an eye on it from home. If you notice new symptoms, feel worse, or are concerned about your health and need to be seen urgently, go to the emergency department."

# (next_node_id: continued_bleeding_follow_up)

# • Monitor Bleeding (current_node_id: monitor_bleeding)

# "While bleeding or spotting in early pregnancy can be alarming, it's actually quite common and doesn't always mean a miscarriage. But keeping an eye on it is important. Always check the color of the blood (brown, pink, or bright red) and keep a note."

# (next_node_id: continued_bleeding_follow_up)

# • Continued Bleeding Follow-Up (current_node_id: continued_bleeding_follow_up)

# "If you continue bleeding, getting checked out by a provider can be helpful. Keep an eye on your bleeding. We'll check in on you again tomorrow. If the bleeding continues or you feel worse, make sure you contact a provider. And remember: If you do not feel well or you're having a medical emergency — especially if you've filled 4 or more super pads in two hours — go to your local ER. If you still have questions or concerns, call PEACE $clinic_phone$, option 5."

# (next_node_id: vaginal_bleeding_follow_up)

# • Vaginal Bleeding - Follow-up (current_node_id: vaginal_bleeding_follow_up)

# "Hey $patient_firstname, just checking on you. How's your vaginal bleeding today? A) Stopped B) Stayed the same C) Gotten heavier Reply with just one letter"

# –– If A (Stopped) –– (next_node_id: bleeding_stopped_response)

# –– If B (Same) –– (next_node_id: persistent_bleeding_response)

# –– If C (Heavier) –– (next_node_id: increased_bleeding_response)

# • Bleeding Stopped Response (current_node_id: bleeding_stopped_response)

# "We're glad to hear it. If anything changes - especially if you begin filling 4 or more super pads in two hours, go to your local ER."

# (next_node_id: null)

# • Persistent Bleeding Response (current_node_id: persistent_bleeding_response)

# "Thanks for sharing—we're sorry to hear your situation hasn't improved. Since your vaginal bleeding has lasted longer than a day, we recommend you call your OB/GYN or $clinic_phone$ and ask for the Early Pregnancy Access Center. If you do not feel well or you're having a medical emergency - especially if you've filled 4 or more super pads in two hours -- go to your local ER."

# (next_node_id: null)

# • Increased Bleeding Response (current_node_id: increased_bleeding_response)

# "Sorry to hear that. Thanks for sharing. Since your vaginal bleeding has lasted longer than a day, and has increased, we recommend you call your OB or $clinic_phone$ & ask for the PEACE clinic for guidance. If you do not have an OB, please go to your local ER. If you're worried or feel like you need urgent help - it's essential to seek medical attention."

# (next_node_id: null)

# • Nausea - 1st Trimester (current_node_id: nausea_1st_trimester)

# "We're sorry to hear it—and we're here to help. Nausea and vomiting are very common during pregnancy. Staying hydrated and eating small, frequent meals can help, along with natural remedies like ginger and vitamin B6. Let's make sure there's nothing you need to be seen for right away. Have you been able to keep food or liquids in your stomach for 24 hours? Reply Y or N"

# –– If Y (Able to Keep Food/Liquids) –– (next_node_id: nausea_management_advice)

# –– If N (Unable to Keep Food/Liquids) –– (next_node_id: nausea_treatment_options)

# • Nausea Management Advice (current_node_id: nausea_management_advice)

# "OK, thanks for letting us know. Nausea and vomiting are very common during pregnancy. To feel better, staying hydrated and eating small, frequent meals (even before you feel hungry) is important. Avoid an empty stomach by taking small sips of water or nibbling on bland snacks throughout the day. Try eating protein-rich foods like meat or beans."

# (next_node_id: nausea_follow_up_warning)

# • Nausea Treatment Options (current_node_id: nausea_treatment_options)

# "OK, thanks for letting us know. There are safe treatment options for you! Your care team at Penn recommends trying a natural remedy like ginger and vitamin B6 (take one 25mg tablet every 8 hours as needed). If this isn't working, you can try unisom – an over-the-counter medication – unless you have an allergy. Let your provider know. You can use this medicine until they call you back."

# (next_node_id: nausea_follow_up_warning)

# • Nausea Follow-Up Warning (current_node_id: nausea_follow_up_warning)

# "If your nausea gets worse and you can't keep foods or liquids down for over 24 hours, contact your provider or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. Don't wait—there are safe treatment options for you!"

# (next_node_id: nausea_1st_trimester_follow_up)

# • Nausea - 1st Trimester Follow-up (current_node_id: nausea_1st_trimester_follow_up)

# "Hey $patient_firstname, just checking on you. How's your nausea today? A) Better B) Stayed the same C) Worse Reply with just the letter"

# –– If A (Better) –– (next_node_id: nausea_improved_response)

# –– If B (Stayed the Same) –– (next_node_id: nausea_same_response)

# –– If C (Worse) –– (next_node_id: nausea_worsened_check)

# • Nausea Improved Response (current_node_id: nausea_improved_response)

# "We're glad to hear it. If anything changes - especially if you can't keep foods or liquids down for 24+ hours, reach out to your OB or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. Don't wait—there are safe treatment options for you."

# (next_node_id: null)

# • Nausea Same Response (current_node_id: nausea_same_response)

# "Thanks for sharing—Sorry you aren't feeling better yet, but we're glad to hear you could keep a little down. Would you like us to check on you tomorrow as well? Reply Y or N"

# –– If Y (Check Tomorrow) –– (next_node_id: schedule_follow_up)

# –– If N (No Follow-Up) –– (next_node_id: nausea_monitoring_advice)

# • Schedule Follow-Up (current_node_id: schedule_follow_up)

# "OK. We're here to help. Let us know if anything changes."

# (next_node_id: null)

# • Nausea Monitoring Advice (current_node_id: nausea_monitoring_advice)

# "OK. We're here to help. Let us know if anything changes. If you can't keep foods or liquids down for 24+ hours, contact your OB or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. There are safe ways to treat this, so don't wait. If you're not feeling well or have a medical emergency, visit your local ER."

# (next_node_id: null)

# • Nausea Worsened Check (current_node_id: nausea_worsened_check)

# "Have you kept food or drinks down since I last checked in? Reply Y or N"

# –– If N (Unable to Keep Food/Drinks) –– (next_node_id: urgent_nausea_response)

# –– If Y (Able to Keep Food/Drinks) –– (next_node_id: null)

# • Urgent Nausea Response (current_node_id: urgent_nausea_response)

# "Sorry to hear that. Thanks for sharing. Since your vomiting has increased and worsened, we recommend you call your OB or $clinic_phone$ & ask for the PEACE clinic for guidance. If you do not have an OB, please visit your local ER. If you're worried or feel like you need urgent help - it's essential to seek medical attention."

# (next_node_id: null)

# • Vomiting - 1st Trimester (current_node_id: vomiting_1st_trimester)

# "Hi $patient_firstName$, It sounds like you're concerned about vomiting. Is that correct? Reply Y or N"

# –– If N (Not Concerned) –– (next_node_id: default_response)

# –– If Y (Concerned) –– (next_node_id: trigger_nausea_triage)

# • Trigger Nausea Triage (current_node_id: trigger_nausea_triage)

# "TRIGGER 2ND NODE → NAUSEA TRIAGE"

# (next_node_id: nausea_1st_trimester)

# (Comment: This node triggers the Nausea - 1st Trimester flow, redirecting to nausea_1st_trimester.)

# • Vomiting - 1st Trimester Follow-up (current_node_id: vomiting_1st_trimester_follow_up)

# "Checking on you, $patient_firstname. How's your vomiting today? A) Better B) Stayed the same C) Worse Reply with just the letter"

# –– If A (Better) –– (next_node_id: vomiting_improved_response)

# –– If B (Stayed the Same) –– (next_node_id: vomiting_same_response)

# –– If C (Worse) –– (next_node_id: vomiting_worsened_response)

# • Vomiting Improved Response (current_node_id: vomiting_improved_response)

# "We're glad to hear it. If anything changes - especially if you can't keep foods or liquids down for 24+ hours, reach out to your OB or call $clinic_phone$ if you have not seen an OB yet. Don't wait—there are safe treatment options for you."

# (next_node_id: null)

# • Vomiting Same Response (current_node_id: vomiting_same_response)

# "Thanks for sharing—Sorry you aren't feeling better yet. Would you like us to check on you tomorrow as well? Reply Y or N"

# –– If Y (Check Tomorrow) –– (next_node_id: schedule_vomiting_follow_up)

# –– If N (No Follow-Up) –– (next_node_id: vomiting_monitoring_advice)

# • Schedule Vomiting Follow-Up (current_node_id: schedule_vomiting_follow_up)

# "OK. We're here to help. Let us know if anything changes."

# (next_node_id: null)

# • Vomiting Monitoring Advice (current_node_id: vomiting_monitoring_advice)

# "OK. We're here to help. Let us know if anything changes. If you can't keep foods or liquids down for 24+ hours, contact your OB or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. If you're not feeling well or have a medical emergency, visit your local ER."

# (next_node_id: null)

# • Vomiting Worsened Response (current_node_id: vomiting_worsened_response)

# "Sorry to hear that. Thanks for sharing. Since your vomiting has increased and worsened, we recommend you call your OB or $clinic_phone$ & ask for the PEACE clinic for guidance. If you do not have an OB, please go to your local ER. If you're worried or feel like you need urgent help - it's essential to seek medical attention."

# (next_node_id: null)

# • Pain - Early Pregnancy (current_node_id: pain_early_pregnancy)

# "We're sorry to hear this. It sounds like you're concerned about pain, is that correct? Reply Y or N"

# –– If N (Not Concerned) –– (next_node_id: default_response)

# –– If Y (Concerned) –– (next_node_id: trigger_vaginal_bleeding_flow_pain)

# • Trigger Vaginal Bleeding Flow (current_node_id: trigger_vaginal_bleeding_flow_pain)

# "Trigger EPS Vaginal Bleeding (First Trimester)"

# (next_node_id: vaginal_bleeding_1st_trimester)

# (Comment: This node triggers the Vaginal Bleeding - 1st Trimester flow, redirecting to vaginal_bleeding_1st_trimester.)

# • Ectopic Pregnancy Concern (current_node_id: ectopic_pregnancy_concern)

# "We're sorry to hear this. It sounds like you're concerned about an ectopic pregnancy, is that correct? Reply Y or N"

# –– If N (Not Concerned) –– (next_node_id: default_response)

# –– If Y (Concerned) –– (next_node_id: trigger_vaginal_bleeding_flow_ectopic)

# • Trigger Vaginal Bleeding Flow (current_node_id: trigger_vaginal_bleeding_flow_ectopic)

# "Trigger EPS Vaginal Bleeding (First Trimester)"

# (next_node_id: vaginal_bleeding_1st_trimester)

# (Comment: This node triggers the Vaginal Bleeding - 1st Trimester flow, redirecting to vaginal_bleeding_1st_trimester.)

# • Menstrual Period Concern (current_node_id: menstrual_period_concern)

# "It sounds like you're concerned about your menstrual period, is that correct? Reply Y or N"

# –– If N (Not Concerned) –– (next_node_id: default_response)

# –– If Y (Concerned) –– (next_node_id: trigger_vaginal_bleeding_flow_menstrual)

# • Trigger Vaginal Bleeding Flow (current_node_id: trigger_vaginal_bleeding_flow_menstrual)

# "EPS Vaginal Bleeding (First Trimester) Let me ask you a few more questions about your medical history to determine the next best steps."

# (next_node_id: vaginal_bleeding_1st_trimester)

# (Comment: This node triggers the Vaginal Bleeding - 1st Trimester flow, redirecting to vaginal_bleeding_1st_trimester.)

# Pregnancy Decision Support Flows

# • Possible Early Pregnancy Loss (current_node_id: possible_early_pregnancy_loss)

# "It sounds like you're concerned about pregnancy loss (miscarriage), is that correct? Reply Y or N"

# –– If N (Not Concerned) –– (next_node_id: default_response)

# –– If Y (Concerned) –– (next_node_id: confirm_pregnancy_loss)

# • Confirm Pregnancy Loss (current_node_id: confirm_pregnancy_loss)

# "We're sorry to hear this. Has a healthcare provider confirmed an early pregnancy loss (that your pregnancy stopped growing)? A) Yes B) No C) Not Sure Reply with just the letter"

# –– If A (Confirmed Loss) –– (next_node_id: support_and_schedule_appointment)

# –– If B (Not Confirmed) –– (next_node_id: trigger_vaginal_bleeding_flow_not_confirmed)

# –– If C (Not Sure) –– (next_node_id: schedule_peace_appointment)

# • Support and Schedule Appointment (current_node_id: support_and_schedule_appointment)

# "We're here to listen and offer support. It's helpful to talk about the options to manage this. We can help schedule you an appointment. Call $clinic_phone$ and ask for the PEACE clinic. We'll check in on you in a few days."

# (next_node_id: null)

# • Trigger Vaginal Bleeding Flow (current_node_id: trigger_vaginal_bleeding_flow_not_confirmed)

# "Trigger Vaginal Bleeding – 1st Trimester"

# (next_node_id: vaginal_bleeding_1st_trimester)

# (Comment: This node triggers the Vaginal Bleeding - 1st Trimester flow, redirecting to vaginal_bleeding_1st_trimester.)

# • Schedule PEACE Appointment (current_node_id: schedule_peace_appointment)

# "Sorry to hear this has been confusing for you. We recommend scheduling an appointment with PEACE so that they can help explain what's going on. Call $clinic_phone$, option 5 and we can help schedule you a visit so that you can get the information you need, and your situation becomes more clear."

# (next_node_id: trigger_vaginal_bleeding_flow_not_sure)

# • Trigger Vaginal Bleeding Flow (current_node_id: trigger_vaginal_bleeding_flow_not_sure)

# "Trigger Vaginal Bleeding – 1st Trimester"

# (next_node_id: vaginal_bleeding_1st_trimester)

# (Comment: This node triggers the Vaginal Bleeding - 1st Trimester flow, redirecting to vaginal_bleeding_1st_trimester.)

# • Undesired Pregnancy - Desires Abortion (current_node_id: undesired_pregnancy_desires_abortion)

# "It sounds like you want to get connected to care for an abortion, is that correct? Reply Y or N"

# –– If N (Not Interested) –– (next_node_id: default_response)

# –– If Y (Interested) –– (next_node_id: abortion_care_connection)

# • Abortion Care Connection (current_node_id: abortion_care_connection)

# "The decision about this pregnancy is yours and no one is better able to decide than you. Please call $clinic_phone$ and ask to be connected to the PEACE clinic (pregnancy early access center). The clinic intake staff will answer your questions and help schedule an abortion. You can also find more information about laws in your state and how to get an abortion at AbortionFinder.org"

# (next_node_id: null)

# • Undesired Pregnancy - Completed Abortion (current_node_id: undesired_pregnancy_completed_abortion)

# "It sounds like you've already had an abortion, is that correct? Reply Y or N"

# –– If N (Not Completed) –– (next_node_id: default_response)

# –– If Y (Completed) –– (next_node_id: post_abortion_care)

# • Post-Abortion Care (current_node_id: post_abortion_care)

# "Caring for yourself after an abortion is important. Follow the instructions given to you. Most people can return to normal activities 1 to 2 days after the procedure. You may have cramps and light bleeding for up to 2 weeks. Call $clinic_phone$, option 5 and ask to be connected to the PEACE clinic (pregnancy early access center) if you have any questions or concerns."

# (next_node_id: offboarding_after_abortion)

# • Offboarding After Abortion (current_node_id: offboarding_after_abortion)

# "Being a part of your care journey has been a real privilege. On behalf of your team at Penn, we hope we've been helpful to you during this time. Since I only guide you through this brief period, I won't be available for texting after today. Remember, you have a lot of resources available from Penn AND your community right at your fingertips."

# (next_node_id: null)

# • Desired Pregnancy Survey (current_node_id: desired_pregnancy_survey)

# "It sounds like you want to get connected to care for your pregnancy, is that correct? Reply Y or N"

# –– If N (Not Interested) –– (next_node_id: default_response)

# –– If Y (Interested) –– (next_node_id: connect_to_prenatal_care)

# • Connect to Prenatal Care (current_node_id: connect_to_prenatal_care)

# "That's something I can definitely do! Call $clinic_phone$ Penn OB/GYN Associates or Dickens Clinic and make an appointment. It's important to receive prenatal care early on (and throughout your pregnancy) to reduce the risk of complications and ensure that both you and your baby are healthy."

# (next_node_id: null)

# • Unsure About Pregnancy Survey (current_node_id: unsure_about_pregnancy_survey)

# "Becoming a parent is a big step. Deciding if you want to continue a pregnancy is a personal decision. Talking openly and honestly with your partner or healthcare team is key. We're here for you. You can also try some thought work here: https://www.pregnancyoptions.info/pregnancy-options-workbook Would you like to get connected to care to discuss your options for pregnancy, is that correct? Reply Y or N"

# –– If N (Not Interested) –– (next_node_id: default_response)

# –– If Y (Interested) –– (next_node_id: connect_to_peace_clinic_for_options)

# • Connect to PEACE Clinic for Options (current_node_id: connect_to_peace_clinic_for_options)

# "Few decisions are greater than this one, but we've got your back. The decision about this pregnancy is yours and no one is better able to decide than you. Please call $clinic_phone$, and ask to be scheduled in the PEACE clinic (pregnancy early access center). They are here to support you no matter what you choose."

# (next_node_id: null)

# Postpartum Support Flows

# • Postpartum Onboarding – Week 1 (current_node_id: postpartum_onboarding_week_1)

# "Hi $patient_firstname$, congratulations on your new baby! Let's get started with a few short messages to support you and your newborn. You can always reply STOP to stop receiving messages." [DAY: 0, TIME: 8 AM]

# (next_node_id: feeding_advice)

# • Feeding Advice (current_node_id: feeding_advice)

# "Feeding your baby is one of the most important parts of newborn care. Feeding your baby at least 8-12 times every 24 hours is normal and important to support their growth. You may need to wake your baby to feed if they're sleepy or jaundiced." [DAY: 0, TIME: 12 PM]

# (next_node_id: track_baby_output)

# • Track Baby Output (current_node_id: track_baby_output)

# "It's important to keep track of your baby's output (wet and dirty diapers) to know they're feeding well. By the time your baby is 5 days old, they should have 5+ wet diapers and 3+ poops per day." [DAY: 0, TIME: 4 PM]

# (next_node_id: jaundice_information)

# • Jaundice Information (current_node_id: jaundice_information)

# "Jaundice is common in newborns and usually goes away on its own. Signs of jaundice include yellowing of the skin or eyes. If you're worried or if your baby isn't feeding well or is hard to wake up, call your pediatrician or visit the ER." [DAY: 0, TIME: 8 PM]

# (next_node_id: schedule_pediatrician_visit)

# • Schedule Pediatrician Visit (current_node_id: schedule_pediatrician_visit)

# "Schedule a pediatrician visit. [Add scheduling link or instructions]" [DAY: 1, TIME: 8 AM]

# (next_node_id: postpartum_check_in)

# • Postpartum Check-In (current_node_id: postpartum_check_in)

# "Hi $patient_firstname$, following up to check on how you're feeling after delivery. The postpartum period is a time of recovery, both physically and emotionally. It's normal to feel tired, sore, or even overwhelmed. You're not alone. Let us know if you need support." [DAY: 1, TIME: 12 PM]

# (next_node_id: urgent_symptoms_warning)

# • Urgent Symptoms Warning (current_node_id: urgent_symptoms_warning)

# "Some symptoms may require urgent care. If you experience chest pain, heavy bleeding, or trouble breathing, call 911 or go to the ER. For other questions or concerns, message us anytime." [DAY: 1, TIME: 4 PM]

# (next_node_id: postpartum_onboarding_week_2)

# • Postpartum Onboarding – Week 2 (current_node_id: postpartum_onboarding_week_2)

# "Hi $patient_firstname$, checking in to see how things are going now that your baby is about a week old. We shared some helpful info last week and want to make sure you're doing okay." [DAY: 7, TIME: 8 AM]

# (next_node_id: emotional_well_being_check)

# • Emotional Well-Being Check (current_node_id: emotional_well_being_check)

# "Hi there—feeling different emotions after delivery is common. You may feel joy, sadness, or both. About 80% of people experience the 'baby blues,' which typically go away in a couple of weeks. If you're not feeling well emotionally or have thoughts of hurting yourself or others, please reach out for help." [DAY: 7, TIME: 12 PM]

# (next_node_id: sids_prevention_advice)

# • SIDS Prevention Advice (current_node_id: sids_prevention_advice)

# "Experts recommend always placing your baby on their back to sleep, in a crib or bassinet without blankets, pillows, or stuffed toys. This reduces the risk of SIDS (Sudden Infant Death Syndrome)." [DAY: 7, TIME: 4 PM]

# (next_node_id: schedule_postpartum_check_in)

# • Schedule Postpartum Check-In (current_node_id: schedule_postpartum_check_in)

# "Reminder to schedule your postpartum check-in." [DAY: 9, TIME: 8 AM]

# (next_node_id: diaper_rash_advice)

# • Diaper Rash Advice (current_node_id: diaper_rash_advice)

# "Diaper rash is common. It can usually be treated with diaper cream and frequent diaper changes. If your baby develops a rash that doesn't go away or seems painful, call your pediatrician." [DAY: 9, TIME: 12 PM]

# (next_node_id: feeding_follow_up)

# • Feeding Follow-Up (current_node_id: feeding_follow_up)

# "Hi $patient_firstname$, checking in again—how is feeding going? Breastfeeding can be challenging at times. It's okay to ask for help from a lactation consultant or your provider. Let us know if you have questions." [DAY: 9, TIME: 4 PM]

# (next_node_id: contraception_reminder)

# • Contraception Reminder (current_node_id: contraception_reminder)

# "Hi $patient_firstname$, just a quick note about contraception. You can get pregnant again even if you haven't gotten your period yet. If you're not ready to be pregnant again soon, it's important to consider your birth control options. Talk to your provider to learn what's right for you." [DAY: 10, TIME: 12 PM]

# (next_node_id: contraception_resources)

# • Contraception Resources (current_node_id: contraception_resources)

# "Birth control is available at no cost with most insurance plans. Let us know if you'd like support connecting to resources." [DAY: 10, TIME: 5 PM]

# (next_node_id: null)

# Emergency Situation Management

# • Emergency Room Survey (current_node_id: emergency_room_survey)

# "It sounds like you are telling me about an emergency. Are you currently in the ER (or on your way)? Reply Y or N"

# –– If Y (In ER) –– (next_node_id: current_er_response)

# –– If N (Not In ER) –– (next_node_id: recent_er_visit_check)

# • Current ER Response (current_node_id: current_er_response)

# "We're sorry to hear and thanks for sharing. Glad you're seeking care. Please let us know if there's anything we can do for you."

# (next_node_id: null)

# • Recent ER Visit Check (current_node_id: recent_er_visit_check)

# "Were you recently discharged from an emergency room visit?"

# –– If Y (Recent ER Visit) –– (next_node_id: share_er_info)

# –– If N (No Recent ER Visit) –– (next_node_id: er_recommendation)

# • Share ER Info (current_node_id: share_er_info)

# "We're sorry to hear about your visit. To help your care team stay in the loop, would you like us to pass on any info? No worries if not, just reply 'no'."

# (next_node_id: follow_up_support)

# • Follow-Up Support (current_node_id: follow_up_support)

# "Let us know if you need anything else."

# (next_node_id: null)

# • ER Recommendation (current_node_id: er_recommendation)

# "If you're not feeling well or have a medical emergency, go to your local ER. If I misunderstood your message, try rephrasing & using short sentences. You may also reply MENU for a list of support options."

# (next_node_id: null)

# Evaluation Surveys

# • Pre-Program Impact Survey (current_node_id: pre_program_impact_survey)

# "Hi there, $patient_firstName$. As you start this program, we'd love to hear your thoughts! We're asking a few questions to understand how you're feeling about managing your early pregnancy."

# (next_node_id: confidence_rating)

# • Confidence Rating (current_node_id: confidence_rating)

# "On a 0-10 scale, with 10 being extremely confident, how confident do you feel in your ability to navigate your needs related to early pregnancy? Reply with a number 0-10"

# (next_node_id: knowledge_rating)

# • Knowledge Rating (current_node_id: knowledge_rating)

# "On a 0-10 scale, with 10 being extremely knowledgeable, how would you rate your knowledge related to early pregnancy? Reply with a number 0-10"

# (next_node_id: thank_you_message)

# • Thank You Message (current_node_id: thank_you_message)

# "Thank you for taking the time to answer these questions. We are looking forward to supporting your health journey."

# (next_node_id: null)

# • Post-Program Impact Survey (current_node_id: post_program_impact_survey)

# "Hi $patient_firstname$, glad you finished the program! Sharing your thoughts would be a huge help in making the program even better for others."

# (next_node_id: post_program_confidence_rating)

# • Post-Program Confidence Rating (current_node_id: post_program_confidence_rating)

# "On a 0-10 scale, with 10 being extremely confident, how confident do you feel in your ability to navigate your needs related to early pregnancy? Reply with a number 0-10"

# (next_node_id: post_program_knowledge_rating)

# • Post-Program Knowledge Rating (current_node_id: post_program_knowledge_rating)

# "On a 0-10 scale, with 10 being extremely knowledgeable, how would you rate your knowledge related to early pregnancy? Reply with a number 0-10"

# (next_node_id: post_program_thank_you)

# • Post-Program Thank You (current_node_id: post_program_thank_you)

# "Thank you for taking the time to answer these questions. We are looking forward to supporting your health journey."

# (next_node_id: null)

# • NPS Quantitative Survey (current_node_id: nps_quantitative_survey)

# "Hi $patient_firstname$, I have two quick questions about using this text messaging service (last time I promise):"

# (next_node_id: likelihood_to_recommend)

# • Likelihood to Recommend (current_node_id: likelihood_to_recommend)

# "On a 0-10 scale, with 10 being 'extremely likely,' how likely are you to recommend this text message program to someone with the same (or similar) situation? Reply with a number 0-10"

# (next_node_id: nps_qualitative_survey)

# • NPS Qualitative Survey (current_node_id: nps_qualitative_survey)

# "Thanks for your response. What's the reason for your score?"

# (next_node_id: feedback_acknowledgment)

# • Feedback Acknowledgment (current_node_id: feedback_acknowledgment)

# "Thanks, your feedback helps us improve future programs."

# (next_node_id: null)

# Menu Responses

# • A. Symptoms Response (current_node_id: menu_a_symptoms_response)

# "We understand questions and concerns come up. By texting this number, you can connect with your question, and I may have an answer. This isn't an emergency line, so it's best to reach out to your doctor if you have an urgent concern by calling $clinic_phone$. If you're worried or feel like this is something serious - it's essential to seek medical attention."

# (next_node_id: symptom_triage)

# • B. Medications Response (current_node_id: menu_b_medications_response)

# "Do you have questions about: A) Medication management B) Medications that are safe in pregnancy C) Abortion medications"

# (next_node_id: medications_follow_up)

# (Comment: Assumes a follow-up response; next_node_id leads to Medications Follow-Up as the next logical step.)

# • Medications Follow-Up (current_node_id: medications_follow_up)

# "Each person — and every medication — is unique, and not all medications are safe to take during pregnancy. Make sure you share what medication you're currently taking with your provider. Your care team will find the best treatment option for you. List of safe meds: https://hspogmembership.org/stages/safe-medications-in-pregnancy"

# (next_node_id: null)

# • C. Appointment Response (current_node_id: menu_c_appointment_response)

# "Unfortunately, I can't see when your appointment is, but you can call the clinic to find out more information. If I don't answer all of your questions, or you have a more complex question, you can contact the Penn care team at $clinic_phone$ who can give you more detailed information about your appointment or general information about what to expect at a visit. Just ask me."

# (next_node_id: null)

# • D. PEACE Visit Response (current_node_id: menu_d_peace_visit_response)

# "The Pregnancy Early Access Center is a support team, which is here to help you make choices throughout the next steps and make sure you have all the information you need. They're like planning for judgment-free care. You can ask all your questions at your visit. You have options, you can place the baby for adoption or you can continue the pregnancy and choose to parent."

# (next_node_id: peace_visit_details)

# • PEACE Visit Details (current_node_id: peace_visit_details)

# "Sometimes, they use an ultrasound to confirm how far along you are to help in discussing options for your pregnancy. If you're considering an abortion, they'll review both types of abortion (medical and surgical) and tell you about the required counseling and consent (must be done at least 24 hours before the procedure). They can also discuss financial assistance and connect you with resources to help cover the cost of care."

# (next_node_id: null)

# • E. Something Else Response (current_node_id: menu_e_something_else_response)

# "Ok, I understand and I might be able to help. Try texting your question to this number. Remember, I do best with short questions that are on one topic. If you need more urgent help or prefer to speak to someone on the phone, you can reach your care team at $clinic_phone$ & ask for your clinic. If you're worried or feel like this is something serious – it's essential to seek medical attention."

# (next_node_id: null)

# • F. Nothing Response (current_node_id: menu_f_nothing_response)

# "OK, remember you can text this number at any time with questions or concerns."

# (next_node_id: null)

# Additional Instructions

# • Always-On Q & A ON FIT (current_node_id: always_on_qa_on_fit)

# "Always-On Q & A ON FIT - Symptom Triage (Nausea, Vomiting & Bleeding + Pregnancy Preference)"

# (next_node_id: symptom_triage)

# (Comment: This node directs to Symptom-Triage as the starting point for Q&A.)

# • General Default Response (current_node_id: general_default_response)

# "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."

# (next_node_id: null)
# """
        



#         flow_instruction_context = f"""
#         Main Patient Journey Flows

#         • **Start Conversation** (current_node_id: start_conversation)
#           "Hi $patient_firstname! I'm here to help you with your healthcare needs. What would you like to talk about today? A) I have a question about symptoms B) I have a question about medications C) I have a question about an appointment D) Information about what to expect at a PEACE visit E) I have a question about a pregnancy test  F) I need help with pregnancy loss  G) Something else H) Nothing at this time Reply with just one letter."
#           (next_node_id: menu_items)

# • **Menu-Items** (current_node_id: menu_items)
#   "What are you looking for today? A) I have a question about symptoms B) I have a question about medications C) I have a question about an appointment D) Information about what to expect at a PEACE visit E) I have a question about a pregnancy test F) I need help with pregnancy loss G) Something else H) Nothing at this time I) Take the Pre-Program Impact Survey J) Take the Post-Program Impact Survey K) Take the NPS Quantitative Survey Reply with just one letter."
#   –– If A (Symptoms) –– (next_node_id: symptoms_response) # Corrected link to use the kept 'symptoms_response' node
#   –– If B (Medications) –– (next_node_id: menu_b_medications_response) # Link to the medications sub-menu
#   –– If C (Appointment) –– (next_node_id: appointment_response)
#   –– If D (PEACE Visit) –– (next_node_id: peace_visit_response_part_1) # Link to the PEACE Visit flow start
#   –– If E (Pregnancy Test) –– (next_node_id: follow_up_confirmation_of_pregnancy_survey)
#   –– If F (Pregnancy Loss) –– (next_node_id: possible_early_pregnancy_loss) # Corrected link to the start of the pregnancy loss flow
#   –– If G (Something Else) –– (next_node_id: something_else_response) # Link to the kept 'something_else_response' node
#   –– If H (Nothing) –– (next_node_id: nothing_response) # Link to the kept 'nothing_response' node
#   –– If I (Pre-Program Impact Survey) –– (next_node_id: pre_program_impact_survey)
#   –– If J (Post-Program Impact Survey) –– (next_node_id: post_program_impact_survey)
#   –– If K (NPS Quantitative Survey) –– (next_node_id: nps_quantitative_survey)

#         • **Onboarding** (current_node_id: onboarding)
#           "Initial patient enrollment with four main branches: Pregnancy Preference Unknown, Desired Pregnancy Preference, Undesired/Unsure Pregnancy Preference, Early Pregnancy Loss. Final pathways to either Offboarding or Program Archived."
#           # Note: This node's next_node_id leads specifically to the pregnancy test survey. Assuming this is intended for this specific onboarding flow snippet.
#           (next_node_id: follow_up_confirmation_of_pregnancy_survey)

#         • **Follow-Up Confirmation of Pregnancy Survey** (current_node_id: follow_up_confirmation_of_pregnancy_survey)
#           "Hi $patient_firstname. As your virtual health buddy, my mission is to help you find the best care for your needs. Have you had a moment to take your home pregnancy test? Reply Y or N"
#           (next_node_id: pregnancy_test_results_nlp_survey)
# # Removed duplicate next_node_id

# • Pregnancy Test Results NLP Survey (current_node_id: pregnancy_test_results_nlp_survey)
# "It sounds like you're sharing your pregnancy test results, is that correct? Reply Y or N"
# –– If N (Pregnancy Test Results) –– (next_node_id: default_response)
# –– If Y (Pregnancy Test Results) –– (next_node_id: pregnancy_test_result_confirmation)

# • Default Response (current_node_id: default_response)
# "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."
# (next_node_id: null)

# • Pregnancy Test Result Confirmation (current_node_id: pregnancy_test_result_confirmation)
# "Were the results positive? Reply Y or N"
# –– If YES (Result Positive) –– (next_node_id: ask_for_lmp)
# –– If NO (Result Negative) –– (next_node_id: negative_test_result_response)

# • Ask for LMP (current_node_id: ask_for_lmp)
# "Sounds good. In order to give you accurate information, it's helpful for me to know the first day of your last menstrual period (LMP). Do you know this date? Reply Y or N (It's OK if you're uncertain)"
# –– If Y (LMP Known) –– (next_node_id: enter_lmp_date)
# –– If N (LMP Unknown) –– (next_node_id: ask_for_edd)

# • Enter LMP Date (current_node_id: enter_lmp_date)
# "Great. Your LMP is a good way to tell your gestational age. Please reply in this format: MM/DD/YYYY"
# (next_node_id: lmp_date_received)

# • LMP Date Received (current_node_id: lmp_date_received)
# "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps. Stay tuned for your estimated gestational age, we're calculating it now."
# (next_node_id: pregnancy_intention_survey)

# • Ask for EDD (current_node_id: ask_for_edd)
# "Not a problem. Do you know your Estimated Due Date? Reply Y or N (again, it's OK if you're uncertain)"
# –– If Y (EDD Known) –– (next_node_id: enter_edd_date)
# –– If N (EDD Unknown) –– (next_node_id: check_penn_medicine_system)

# • Enter EDD Date (current_node_id: enter_edd_date)
# "Great. Please reply in this format: MM/DD/YYYY"
# (next_node_id: edd_date_received)

# • EDD Date Received (current_node_id: edd_date_received)
# "Perfect. Thanks so much. Over the next few days we're here for you and ready to help with next steps. Stay tuned for your estimated gestational age, we're calculating it now."
# (next_node_id: pregnancy_intention_survey)

# • Check Penn Medicine System (current_node_id: check_penn_medicine_system)
# "We know it can be hard to keep track of periods sometimes. Have you been seen in the Penn Medicine system? Reply Y or N"
# –– If Y (Seen in Penn System) –– (next_node_id: penn_system_confirmation)
# –– If N (Not Seen in Penn System) –– (next_node_id: register_as_new_patient)

# • Penn System Confirmation (current_node_id: penn_system_confirmation)
# "Perfect. Over the next few days we're here for you and ready to help with your next moves. Stay tuned!"
# (next_node_id: pregnancy_intention_survey)

# • Register as New Patient (current_node_id: register_as_new_patient)
# "Not a problem. Contact the call center $clinic_phone$ and have them add you as a 'new patient'. This way, if you need any assistance in the future, we'll be able to help you quickly."
# (next_node_id: pregnancy_intention_survey)

# • Negative Test Result Response (current_node_id: negative_test_result_response)
# "Thanks for sharing. If you have any questions or if there's anything you'd like to talk about, we're here for you. Contact the call center $clinic_phone$ for any follow-ups & to make an appointment with your OB/GYN."
# (next_node_id: offboarding_after_negative_result)

# • Offboarding After Negative Result (current_node_id: offboarding_after_negative_result)
# "Being a part of your care journey has been a real privilege. Since I only guide you through this brief period, I won't be available for texting after today. If you find yourself pregnant in the future, text me back at this number, and I'll be here to support you once again."
# (next_node_id: null)

# • Pregnancy Intention Survey (current_node_id: pregnancy_intention_survey)
# "$patient_firstName$, pregnancy can stir up many different emotions. These can range from uncertainty and regret to joy and happiness. You might even feel multiple emotions at the same time. It's okay to have these feelings. We're here to help support you through it all. I'm checking in on how you're feeling about being pregnant. Are you: A) Excited B) Not sure C) Not excited Reply with just 1 letter"
# –– If A (Excited) –– (next_node_id: excited_response)
# –– If B (Not Sure) –– (next_node_id: not_sure_response)
# –– If C (Not Excited) –– (next_node_id: not_excited_response)

# • Excited Response (current_node_id: excited_response)
# "Well that is exciting news! Some people feel excited, and want to continue their pregnancy, and others aren't sure. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you."
# (next_node_id: care_options_prompt)

# • Not Sure Response (current_node_id: not_sure_response)
# "We're here to support you. Some people feel excitement, and want to continue their pregnancy, and others aren't sure or want an abortion. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you."
# (next_node_id: care_options_prompt)

# • Not Excited Response (current_node_id: not_excited_response)
# "We're here to support you. Some people feel excitement, and want to continue their pregnancy, and others aren't sure or want an abortion. The next step is connecting with a provider. I'm here to assist you in navigating your options as you choose the right care for you."
# (next_node_id: care_options_prompt)

# • Care Options Prompt (current_node_id: care_options_prompt)
# "Would you prefer us to connect you with providers who can help with: A) Continuing my pregnancy B) Talking with me about what my options are C) Getting an abortion Reply with just 1 letter"
# –– If A (Continuing Pregnancy) –– (next_node_id: prenatal_provider_check)
# –– If B (Options) –– (next_node_id: connect_to_peace_clinic) # This node name seems to imply connecting for care, not just options discussion - keeping as is based on provided text.
# –– If C (Abortion) –– (next_node_id: connect_to_peace_for_abortion)

# • Prenatal Provider Check (current_node_id: prenatal_provider_check)
# "Do you have a prenatal provider? Reply Y or N"
# –– If Y (Has Prenatal Provider) –– (next_node_id: schedule_appointment)
# –– If N (No Prenatal Provider) –– (next_node_id: schedule_with_penn_obgyn)

# • Schedule Appointment (current_node_id: schedule_appointment)
# "Great, it sounds like you're on the right track! Call $clinic_phone$ to make an appointment."
# (next_node_id: null)

# • Schedule with Penn OB/GYN (current_node_id: schedule_with_penn_obgyn)
# "It's important to receive prenatal care early on. Sometimes it takes a few weeks to get in. Call $clinic_phone$ to schedule an appointment with Penn OB/GYN Associates or Dickens Clinic."
# (next_node_id: null)

# • Connect to PEACE Clinic (current_node_id: connect_to_peace_clinic)
# "We understand your emotions, and it's important to take the necessary time to navigate through them. The team at The Pregnancy Early Access Center (PEACE) provides abortion, miscarriage management, and pregnancy prevention. Call $clinic_phone$ to schedule an appointment with PEACE. https://www.pennmedicine.org/make-an-appointment"
# (next_node_id: null)

# • Connect to PEACE for Abortion (current_node_id: connect_to_peace_for_abortion)
# "Call $clinic_phone$ to be scheduled with PEACE. https://www.pennmedicine.org/make-an-appointment We'll check back with you to make sure you're connected to care. We have a few more questions before your visit. It'll help us find the right care for you."
# # Note: This node description mentions asking more questions, but the next_node_id is null. Keeping as is.
# (next_node_id: null)

# Symptom Management Flows

# # Removed duplicate Menu-Items node (A-F)
# # Removed duplicate A. Symptoms Response node

# • Symptoms Response (current_node_id: symptoms_response)
#   "We understand questions and concerns come up. You can try texting this number with your question, and I may have an answer. This isn't an emergency line, so it’s best to reach out to your provider if you have an urgent concern by calling $clinic_phone$. If you're worried or feel like this is something serious – it's essential to seek medical attention."
#   (next_node_id: symptom_triage) # Correctly links to the triage node

# • B. Medications Response (current_node_id: menu_b_medications_response)
#   "Do you have questions about: A) Medication management B) Medications that are safe in pregnancy C) Abortion medications"
#   # Corrected next_node_ids to point to the combined medication info node.
#   –– If A (Medication management) –– (next_node_id: medications_info)
#   –– If B (Safe medications) –– (next_node_id: medications_info)
#   –– If C (Abortion medications) –– (next_node_id: null) # No specific flow defined for this option in the provided text, pointing to null.

# • Medications Info (current_node_id: medications_info)
#   # Renamed node to consolidate the medication info message.
#   "Each person — and every medication — is unique, and not all medications are safe to take during pregnancy. Make sure you share what medication you're currently taking with your provider. Your care team will find the best treatment option for you. List of safe meds: https://hspogmembership.org/stages/safe-medications-in-pregnancy"
#   (next_node_id: null)
# # Removed duplicate Medications Follow-Up node

# • Appointment Response (current_node_id: appointment_response) # Kept as linked by the menu
#   "Unfortunately, I can’t see when your appointment is, but you can call the clinic to find out more information. If I don’t answer all of your questions, or you have a more complex question, you can contact the Penn care team at $clinic_phone$ who can give you further instructions. I can also provide some general information about what to expect at a visit. Just ask me."
#   (next_node_id: null)
# # Removed duplicate C. Appointment Response node

# • PEACE Visit Response Part 1 (current_node_id: peace_visit_response_part_1) # Kept as linked by the menu
#   "The Pregnancy Early Access Center is a support team who's here to help you think through the next steps and make sure you have all the information you need. They're a listening ear, judgment-free and will support any decision you make. You can have an abortion, you can place the baby for adoption or you can continue the pregnancy and choose to parent. They are there to listen to you and answer any of your questions."
#   (next_node_id: peace_visit_response_part_2)

# • PEACE Visit Response Part 2 (current_node_id: peace_visit_response_part_2)
#   "Sometimes, they use an ultrasound to confirm how far along you are to help in discussing options for your pregnancy. If you're considering an abortion, they'll review both types of abortion (medical and surgical) and tell you about the required counseling and consent (must be done at least 24 hours before the procedure). They can also discuss financial assistance and connect you with resources to help cover the cost of care."
#   (next_node_id: null)
# # Removed duplicate D. PEACE Visit Response / Details nodes

# • Something Else Response (current_node_id: something_else_response) # Kept and renamed the menu version for consistency
#   "Ok, I understand and I might be able to help. Try texting your question to this number. Remember, I do best with short questions that are on one topic. If you need more urgent help or prefer to speak to someone on the phone, you can reach your care team at $clinic_phone$ & ask for your clinic. If you're worried or feel like this is something serious – it's essential to seek medical attention."
#   (next_node_id: null)
# # Removed duplicate E. Something Else Response node

# • Nothing Response (current_node_id: nothing_response) # Kept the first one and removed the menu version
#   "OK, remember you can text this number at any time with questions or concerns."
#   (next_node_id: null)
# # Removed duplicate F. Nothing Response node

# • Symptom-Triage (current_node_id: symptom_triage)
#   "What symptom are you experiencing? Reply 'Bleeding', 'Nausea', 'Vomiting', 'Pain', or 'Other'"
#   –– If Bleeding –– (next_node_id: vaginal_bleeding_1st_trimester)
#   –– If Nausea –– (next_node_id: nausea_1st_trimester)
#   –– If Vomiting –– (next_node_id: vomiting_1st_trimester)
#   –– If Pain –– (next_node_id: pain_early_pregnancy)
#   –– If Other –– (next_node_id: default_response)

# • Vaginal Bleeding - 1st Trimester (current_node_id: vaginal_bleeding_1st_trimester)
#   "Let me ask a few more questions about your medical history to determine the next best steps. Have you ever had an ectopic pregnancy (this is a pregnancy in your tube or anywhere outside of your uterus)? Reply Y or N"
#   –– If Y (Previous Ectopic Pregnancy) –– (next_node_id: immediate_provider_visit)
#   –– If N (No Previous Ectopic Pregnancy) –– (next_node_id: heavy_bleeding_check)

# • Immediate Provider Visit (current_node_id: immediate_provider_visit)
#   "Considering your past history, you should be seen by a provider immediately. Now: Call your OB/GYN ASAP (Call $clinic_phone$ to make an urgent appointment with PEACE – the Early Pregnancy Access Center – if you do not have a provider) If you're not feeling well or have a medical emergency, visit your local ER."
#   (next_node_id: null)

# • Heavy Bleeding Check (current_node_id: heavy_bleeding_check)
#   "Over the past 2 hours, is your bleeding so heavy that you've filled 4 or more super pads? Reply Y or N"
#   –– If Y (Heavy Bleeding) –– (next_node_id: urgent_provider_visit_for_heavy_bleeding)
#   –– If N (No Heavy Bleeding) –– (next_node_id: pain_or_cramping_check)

# • Urgent Provider Visit for Heavy Bleeding (current_node_id: urgent_provider_visit_for_heavy_bleeding)
#   "This amount of bleeding during pregnancy means you should be seen by a provider immediately. Now: Call your OB/GYN. (Call $clinic_phone$, option 5 to make an urgent appointment with PEACE – the Early Pregnancy Access Center) If you're not feeling well or have a medical emergency, visit your local ER."
#   (next_node_id: null)

# • Pain or Cramping Check (current_node_id: pain_or_cramping_check)
#   "Are you in any pain or cramping? Reply Y or N"
#   –– If Y (Pain or Cramping) –– (next_node_id: er_visit_check_during_pregnancy)
#   –– If N (No Pain or Cramping) –– (next_node_id: monitor_bleeding)

# • ER Visit Check During Pregnancy (current_node_id: er_visit_check_during_pregnancy)
#   "Have you been to the ER during this pregnancy? Reply Y or N"
#   –– If Y (Been to ER) –– (next_node_id: report_bleeding_to_provider)
#   –– If N (Not Been to ER) –– (next_node_id: monitor_bleeding_at_home)

# • Report Bleeding to Provider (current_node_id: report_bleeding_to_provider)
#   "Any amount of bleeding during pregnancy should be reported to a provider. Call your provider for guidance."
#   (next_node_id: continued_bleeding_follow_up)

# • Monitor Bleeding at Home (current_node_id: monitor_bleeding_at_home)
#   "While bleeding or spotting in early pregnancy can be alarming, it's pretty common. Based on your exam in the ER, it's okay to keep an eye on it from home. If you notice new symptoms, feel worse, or are concerned about your health and need to be seen urgently, go to the emergency department."
#   (next_node_id: continued_bleeding_follow_up)

# • Monitor Bleeding (current_node_id: monitor_bleeding)
#   "While bleeding or spotting in early pregnancy can be alarming, it's actually quite common and doesn't always mean a miscarriage. But keeping an eye on it is important. Always check the color of the blood (brown, pink, or bright red) and keep a note."
#   (next_node_id: continued_bleeding_follow_up)

# • Continued Bleeding Follow-Up (current_node_id: continued_bleeding_follow_up)
#   "If you continue bleeding, getting checked out by a provider can be helpful. Keep an eye on your bleeding. We'll check in on you again tomorrow. If the bleeding continues or you feel worse, make sure you contact a provider. And remember: If you do not feel well or you're having a medical emergency — especially if you've filled 4 or more super pads in two hours — go to your local ER. If you still have questions or concerns, call PEACE $clinic_phone$, option 5."
#   (next_node_id: vaginal_bleeding_follow_up)

# • Vaginal Bleeding - Follow-up (current_node_id: vaginal_bleeding_follow_up)
#   "Hey $patient_firstname, just checking on you. How's your vaginal bleeding today? A) Stopped B) Stayed the same C) Gotten heavier Reply with just one letter"
#   –– If A (Stopped) –– (next_node_id: bleeding_stopped_response)
#   –– If B (Same) –– (next_node_id: persistent_bleeding_response)
#   –– If C (Heavier) –– (next_node_id: increased_bleeding_response)

# • Bleeding Stopped Response (current_node_id: bleeding_stopped_response)
#   "We're glad to hear it. If anything changes - especially if you begin filling 4 or more super pads in two hours, go to your local ER."
#   (next_node_id: null)

# • Persistent Bleeding Response (current_node_id: persistent_bleeding_response)
#   "Thanks for sharing—we're sorry to hear your situation hasn't improved. Since your vaginal bleeding has lasted longer than a day, we recommend you call your OB/GYN or $clinic_phone$ and ask for the Early Pregnancy Access Center. If you do not feel well or you're having a medical emergency - especially if you've filled 4 or more super pads in two hours -- go to your local ER."
#   (next_node_id: null)

# • Increased Bleeding Response (current_node_id: increased_bleeding_response)
#   "Sorry to hear that. Thanks for sharing. Since your vaginal bleeding has lasted longer than a day, and has increased, we recommend you call your OB or $clinic_phone$ & ask for the PEACE clinic for guidance. If you do not have an OB, please go to your local ER. If you're worried or feel like you need urgent help - it's essential to seek medical attention."
#   (next_node_id: null)

# • Nausea - 1st Trimester (current_node_id: nausea_1st_trimester)
#   "We're sorry to hear it—and we're here to help. Nausea and vomiting are very common during pregnancy. Staying hydrated and eating small, frequent meals can help, along with natural remedies like ginger and vitamin B6. Let's make sure there's nothing you need to be seen for right away. Have you been able to keep food or liquids in your stomach for 24 hours? Reply Y or N"
#   –– If Y (Able to Keep Food/Liquids) –– (next_node_id: nausea_management_advice)
#   –– If N (Unable to Keep Food/Liquids) –– (next_node_id: nausea_treatment_options)

# • Nausea Management Advice (current_node_id: nausea_management_advice)
#   "OK, thanks for letting us know. Nausea and vomiting are very common during pregnancy. To feel better, staying hydrated and eating small, frequent meals (even before you feel hungry) is important. Avoid an empty stomach by taking small sips of water or nibbling on bland snacks throughout the day. Try eating protein-rich foods like meat or beans."
#   (next_node_id: nausea_follow_up_warning)

# • Nausea Treatment Options (current_node_id: nausea_treatment_options)
#   "OK, thanks for letting us know. There are safe treatment options for you! Your care team at Penn recommends trying a natural remedy like ginger and vitamin B6 (take one 25mg tablet every 8 hours as needed). If this isn't working, you can try unisom – an over-the-counter medication – unless you have an allergy. Let your provider know. You can use this medicine until they call you back."
#   (next_node_id: nausea_follow_up_warning)

# • Nausea Follow-Up Warning (current_node_id: nausea_follow_up_warning)
#   "If your nausea gets worse and you can't keep foods or liquids down for over 24 hours, contact your provider or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. Don't wait—there are safe treatment options for you!"
#   (next_node_id: nausea_1st_trimester_follow_up)

# • Nausea - 1st Trimester Follow-up (current_node_id: nausea_1st_trimester_follow_up)
#   "Hey $patient_firstname, just checking on you. How's your nausea today? A) Better B) Stayed the same C) Worse Reply with just the letter"
#   –– If A (Better) –– (next_node_id: nausea_improved_response)
#   –– If B (Stayed the Same) –– (next_node_id: nausea_same_response)
#   –– If C (Worse) –– (next_node_id: nausea_worsened_check)

# • Nausea Improved Response (current_node_id: nausea_improved_response)
#   "We're glad to hear it. If anything changes - especially if you can't keep foods or liquids down for 24+ hours, reach out to your OB or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. Don't wait—there are safe treatment options for you."
#   (next_node_id: null)

# • Nausea Same Response (current_node_id: nausea_same_response)
#   "Thanks for sharing—Sorry you aren't feeling better yet, but we're glad to hear you could keep a little down. Would you like us to check on you tomorrow as well? Reply Y or N"
#   –– If Y (Check Tomorrow) –– (next_node_id: schedule_follow_up)
#   –– If N (No Follow-Up) –– (next_node_id: nausea_monitoring_advice)

# • Schedule Follow-Up (current_node_id: schedule_follow_up)
#   "OK. We're here to help. Let us know if anything changes."
#   (next_node_id: null)

# • Nausea Monitoring Advice (current_node_id: nausea_monitoring_advice)
#   "OK. We're here to help. Let us know if anything changes. If you can't keep foods or liquids down for 24+ hours, contact your OB or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. There are safe ways to treat this, so don't wait. If you're not feeling well or have a medical emergency, visit your local ER."
#   (next_node_id: null)

# • Nausea Worsened Check (current_node_id: nausea_worsened_check)
#   "Have you kept food or drinks down since I last checked in? Reply Y or N"
#   –– If N (Unable to Keep Food/Drinks) –– (next_node_id: urgent_nausea_response)
#   –– If Y (Able to Keep Food/Drinks) –– (next_node_id: null)

# • Urgent Nausea Response (current_node_id: urgent_nausea_response)
#   "Sorry to hear that. Thanks for sharing. Since your vomiting has increased and worsened, we recommend you call your OB or $clinic_phone$ & ask for the PEACE clinic for guidance. If you do not have an OB, please go to your local ER. If you're worried or feel like you need urgent help - it's essential to seek medical attention."
#   (next_node_id: null)

# • Vomiting - 1st Trimester (current_node_id: vomiting_1st_trimester)
#   "Hi $patient_firstName$, It sounds like you're concerned about vomiting. Is that correct? Reply Y or N"
#   –– If N (Not Concerned) –– (next_node_id: default_response)
#   –– If Y (Concerned) –– (next_node_id: trigger_nausea_triage) # Points to nausea triage as defined

# • Trigger Nausea Triage (current_node_id: trigger_nausea_triage)
#   "TRIGGER 2ND NODE → NAUSEA TRIAGE"
#   (next_node_id: nausea_1st_trimester)
#   (Comment: This node triggers the Nausea - 1st Trimester flow, redirecting to nausea_1st_trimester.)

# • Vomiting - 1st Trimester Follow-up (current_node_id: vomiting_1st_trimester_follow_up)
#   # Note: This vomiting follow-up flow exists but is not currently linked from any node in the provided text.
#   "Checking on you, $patient_firstname. How's your vomiting today? A) Better B) Stayed the same C) Worse Reply with just the letter"
#   –– If A (Better) –– (next_node_id: vomiting_improved_response)
#   –– If B (Stayed the Same) –– (next_node_id: vomiting_same_response)
#   –– If C (Worse) –– (next_node_id: vomiting_worsened_response)

# • Vomiting Improved Response (current_node_id: vomiting_improved_response)
#   "We're glad to hear it. If anything changes - especially if you can't keep foods or liquids down for 24+ hours, reach out to your OB or call $clinic_phone$ if you have not seen an OB yet. Don't wait—there are safe treatment options for you."
#   (next_node_id: null)

# • Vomiting Same Response (current_node_id: vomiting_same_response)
#   "Thanks for sharing—Sorry you aren't feeling better yet. Would you like us to check on you tomorrow as well? Reply Y or N"
#   –– If Y (Check Tomorrow) –– (next_node_id: schedule_vomiting_follow_up)
#   –– If N (No Follow-Up) –– (next_node_id: vomiting_monitoring_advice)

# • Schedule Vomiting Follow-Up (current_node_id: schedule_vomiting_follow_up)
#   "OK. We're here to help. Let us know if anything changes."
#   (next_node_id: null)

# • Vomiting Monitoring Advice (current_node_id: vomiting_monitoring_advice)
#   "OK. We're here to help. Let us know if anything changes. If you can't keep foods or liquids down for 24+ hours, contact your OB or call $clinic_phone$ if you haven't seen an OB yet & ask for the PEACE clinic. If you're not feeling well or have a medical emergency, visit your local ER."
#   (next_node_id: null)

# • Vomiting Worsened Response (current_node_id: vomiting_worsened_response)
#   "Sorry to hear that. Thanks for sharing. Since your vomiting has increased and worsened, we recommend you call your OB or $clinic_phone$ & ask for the PEACE clinic for guidance. If you do not have an OB, please go to your local ER. If you're worried or feel like you need urgent help - it's essential to seek medical attention."
#   (next_node_id: null)

# • Pain - Early Pregnancy (current_node_id: pain_early_pregnancy)
#   "We're sorry to hear this. It sounds like you're concerned about pain, is that correct? Reply Y or N"
#   –– If N (Not Concerned) –– (next_node_id: default_response)
#   –– If Y (Concerned) –– (next_node_id: trigger_vaginal_bleeding_flow) # Pointing to the consolidated trigger node

# # Consolidated Trigger Node for Vaginal Bleeding Flow
# • Trigger Vaginal Bleeding Flow (current_node_id: trigger_vaginal_bleeding_flow)
#   "Trigger EPS Vaginal Bleeding (First Trimester)"
#   (next_node_id: vaginal_bleeding_1st_trimester)
#   (Comment: This node triggers the Vaginal Bleeding - 1st Trimester flow, redirecting to vaginal_bleeding_1st_trimester.)
# # Removed duplicate trigger nodes for pain, ectopic, menstrual, not_confirmed, not_sure

# • Ectopic Pregnancy Concern (current_node_id: ectopic_pregnancy_concern)
#   "We're sorry to hear this. It sounds like you're concerned about an ectopic pregnancy, is that correct? Reply Y or N"
#   –– If N (Not Concerned) –– (next_node_id: default_response)
#   –– If Y (Concerned) –– (next_node_id: trigger_vaginal_bleeding_flow) # Pointing to the consolidated trigger node

# • Menstrual Period Concern (current_node_id: menstrual_period_concern)
#   "It sounds like you're concerned about your menstrual period, is that correct? Reply Y or N"
#   –– If N (Not Concerned) –– (next_node_id: default_response)
#   –– If Y (Concerned) –– (next_node_id: trigger_vaginal_bleeding_flow) # Pointing to the consolidated trigger node

# Pregnancy Decision Support Flows

# • Possible Early Pregnancy Loss (current_node_id: possible_early_pregnancy_loss) # This is the target for Menu-Items F
#   "It sounds like you're concerned about pregnancy loss (miscarriage), is that correct? Reply Y or N"
#   –– If N (Not Concerned) –– (next_node_id: default_response)
#   –– If Y (Concerned) –– (next_node_id: confirm_pregnancy_loss)

# • Confirm Pregnancy Loss (current_node_id: confirm_pregnancy_loss)
#   "We're sorry to hear this. Has a healthcare provider confirmed an early pregnancy loss (that your pregnancy stopped growing)? A) Yes B) No C) Not Sure Reply with just the letter"
#   –– If A (Confirmed Loss) –– (next_node_id: support_and_schedule_appointment)
#   –– If B (Not Confirmed) –– (next_node_id: trigger_vaginal_bleeding_flow) # Pointing to the consolidated trigger node
#   –– If C (Not Sure) –– (next_node_id: schedule_peace_appointment)

# • Support and Schedule Appointment (current_node_id: support_and_schedule_appointment)
#   "We're here to listen and offer support. It's helpful to talk about the options to manage this. We can help schedule you an appointment. Call $clinic_phone$ and ask for the PEACE clinic. We'll check in on you in a few days."
#   (next_node_id: null)

# • Schedule PEACE Appointment (current_node_id: schedule_peace_appointment)
#   "Sorry to hear this has been confusing for you. We recommend scheduling an appointment with PEACE so that they can help explain what's going on. Call $clinic_phone$, option 5 and we can help schedule you a visit so that you can get the information you need, and your situation becomes more clear."
#   (next_node_id: trigger_vaginal_bleeding_flow) # Pointing to the consolidated trigger node

# • Undesired Pregnancy - Desires Abortion (current_node_id: undesired_pregnancy_desires_abortion)
#   "It sounds like you want to get connected to care for an abortion, is that correct? Reply Y or N"
#   –– If N (Not Interested) –– (next_node_id: default_response)
#   –– If Y (Interested) –– (next_node_id: abortion_care_connection)

# • Abortion Care Connection (current_node_id: abortion_care_connection)
#   "The decision about this pregnancy is yours and no one is better able to decide than you. Please call $clinic_phone$ and ask to be connected to the PEACE clinic (pregnancy early access center). The clinic intake staff will answer your questions and help schedule an abortion. You can also find more information about laws in your state and how to get an abortion at AbortionFinder.org"
#   (next_node_id: null)

# • Undesired Pregnancy - Completed Abortion (current_node_id: undesired_pregnancy_completed_abortion)
#   "It sounds like you've already had an abortion, is that correct? Reply Y or N"
#   –– If N (Not Completed) –– (next_node_id: default_response)
#   –– If Y (Completed) –– (next_node_id: post_abortion_care)

# • Post-Abortion Care (current_node_id: post_abortion_care)
#   "Caring for yourself after an abortion is important. Follow the instructions given to you. Most people can return to normal activities 1 to 2 days after the procedure. You may have cramps and light bleeding for up to 2 weeks. Call $clinic_phone$, option 5 and ask to be connected to the PEACE clinic (pregnancy early access center) if you have any questions or concerns."
#   (next_node_id: offboarding_after_abortion)

# • Offboarding After Abortion (current_node_id: offboarding_after_abortion)
#   "Being a part of your care journey has been a real privilege. On behalf of your team at Penn, we hope we've been helpful to you during this time. Since I only guide you through this brief period, I won't be available for texting after today. Remember, you have a lot of resources available from Penn AND your community right at your fingertips."
#   (next_node_id: null)

# • Desired Pregnancy Survey (current_node_id: desired_pregnancy_survey)
#   "It sounds like you want to get connected to care for your pregnancy, is that correct? Reply Y or N"
#   –– If N (Not Interested) –– (next_node_id: default_response)
#   –– If Y (Interested) –– (next_node_id: connect_to_prenatal_care)

# • Connect to Prenatal Care (current_node_id: connect_to_prenatal_care)
#   "That's something I can definitely do! Call $clinic_phone$ Penn OB/GYN Associates or Dickens Clinic and make an appointment. It's important to receive prenatal care early on (and throughout your pregnancy) to reduce the risk of complications and ensure that both you and your baby are healthy."
#   (next_node_id: null)

# • Unsure About Pregnancy Survey (current_node_id: unsure_about_pregnancy_survey)
#   "Becoming a parent is a big step. Deciding if you want to continue a pregnancy is a personal decision. Talking openly and honestly with your partner or healthcare team is key. We're here for you. You can also try some thought work here: https://www.pregnancyoptions.info/pregnancy-options-workbook Would you like to get connected to care to discuss your options for pregnancy, is that correct? Reply Y or N"
#   –– If N (Not Interested) –– (next_node_id: default_response)
#   –– If Y (Interested) –– (next_node_id: connect_to_peace_clinic_for_options)

# • Connect to PEACE Clinic for Options (current_node_id: connect_to_peace_clinic_for_options)
#   "Few decisions are greater than this one, but we've got your back. The decision about this pregnancy is yours and no one is better able to decide than you. Please call $clinic_phone$, and ask to be scheduled in the PEACE clinic (pregnancy early access center). They are here to support you no matter what you choose."
#   (next_node_id: null)

# Postpartum Support Flows

# • Postpartum Onboarding – Week 1 (current_node_id: postpartum_onboarding_week_1)
#   "Hi $patient_firstname$, congratulations on your new baby! Let's get started with a few short messages to support you and your newborn. You can always reply STOP to stop receiving messages." [DAY: 0, TIME: 8 AM]
#   (next_node_id: feeding_advice)

# • Feeding Advice (current_node_id: feeding_advice)
#   "Feeding your baby is one of the most important parts of newborn care. Feeding your baby at least 8-12 times every 24 hours is normal and important to support their growth. You may need to wake your baby to feed if they're sleepy or jaundiced." [DAY: 0, TIME: 12 PM]
#   (next_node_id: track_baby_output)

# • Track Baby Output (current_node_id: track_baby_output)
#   "It's important to keep track of your baby's output (wet and dirty diapers) to know they're feeding well. By the time your baby is 5 days old, they should have 5+ wet diapers and 3+ poops per day." [DAY: 0, TIME: 4 PM]
#   (next_node_id: jaundice_information)

# • Jaundice Information (current_node_id: jaundice_information)
#   "Jaundice is common in newborns and usually goes away on its own. Signs of jaundice include yellowing of the skin or eyes. If you're worried or if your baby isn't feeding well or is hard to wake up, call your pediatrician or visit the ER." [DAY: 0, TIME: 8 PM]
#   (next_node_id: schedule_pediatrician_visit)

# • Schedule Pediatrician Visit (current_node_id: schedule_pediatrician_visit)
#   "Schedule a pediatrician visit. [Add scheduling link or instructions]" [DAY: 1, TIME: 8 AM]
#   (next_node_id: postpartum_check_in)

# • Postpartum Check-In (current_node_id: postpartum_check_in)
#   "Hi $patient_firstname$, following up to check on how you're feeling after delivery. The postpartum period is a time of recovery, both physically and emotionally. It's normal to feel tired, sore, or even overwhelmed. You're not alone. Let us know if you need support." [DAY: 1, TIME: 12 PM]
#   (next_node_id: urgent_symptoms_warning)

# • Urgent Symptoms Warning (current_node_id: urgent_symptoms_warning)
#   "Some symptoms may require urgent care. If you experience chest pain, heavy bleeding, or trouble breathing, call 911 or go to the ER. For other questions or concerns, message us anytime." [DAY: 1, TIME: 4 PM]
#   (next_node_id: postpartum_onboarding_week_2)

# • Postpartum Onboarding – Week 2 (current_node_id: postpartum_onboarding_week_2)
#   "Hi $patient_firstname$, checking in to see how things are going now that your baby is about a week old. We shared some helpful info last week and want to make sure you're doing okay." [DAY: 7, TIME: 8 AM]
#   (next_node_id: emotional_well_being_check)

# • Emotional Well-Being Check (current_node_id: emotional_well_being_check)
#   "Hi there—feeling different emotions after delivery is common. You may feel joy, sadness, or both. About 80% of people experience the 'baby blues,' which typically go away in a couple of weeks. If you're not feeling well emotionally or have thoughts of hurting yourself or others, please reach out for help." [DAY: 7, TIME: 12 PM]
#   (next_node_id: sids_prevention_advice)

# • SIDS Prevention Advice (current_node_id: sids_prevention_advice)
#   "Experts recommend always placing your baby on their back to sleep, in a crib or bassinet without blankets, pillows, or stuffed toys. This reduces the risk of SIDS (Sudden Infant Death Syndrome)." [DAY: 7, TIME: 4 PM]
#   (next_node_id: schedule_postpartum_check_in)

# • Schedule Postpartum Check-In (current_node_id: schedule_postpartum_check_in)
#   "Reminder to schedule your postpartum check-in." [DAY: 9, TIME: 8 AM]
#   (next_node_id: diaper_rash_advice)

# • Diaper Rash Advice (current_node_id: diaper_rash_advice)
#   "Diaper rash is common. It can usually be treated with diaper cream and frequent diaper changes. If your baby develops a rash that doesn't go away or seems painful, call your pediatrician." [DAY: 9, TIME: 12 PM]
#   (next_node_id: feeding_follow_up)

# • Feeding Follow-Up (current_node_id: feeding_follow_up)
#   "Hi $patient_firstname$, checking in again—how is feeding going? Breastfeeding can be challenging at times. It's okay to ask for help from a lactation consultant or your provider. Let us know if you have questions." [DAY: 9, TIME: 4 PM]
#   (next_node_id: contraception_reminder)

# • Contraception Reminder (current_node_id: contraception_reminder)
#   "Hi $patient_firstname$, just a quick note about contraception. You can get pregnant again even if you haven't gotten your period yet. If you're not ready to be pregnant again soon, it's important to consider your birth control options. Talk to your provider to learn what's right for you." [DAY: 10, TIME: 12 PM]
#   (next_node_id: contraception_resources)

# • Contraception Resources (current_node_id: contraception_resources)
#   "Birth control is available at no cost with most insurance plans. Let us know if you'd like support connecting to resources." [DAY: 10, TIME: 5 PM]
#   (next_node_id: null)

# Emergency Situation Management

# • Emergency Room Survey (current_node_id: emergency_room_survey)
#   "It sounds like you are telling me about an emergency. Are you currently in the ER (or on your way)? Reply Y or N"
#   –– If Y (In ER) –– (next_node_id: current_er_response)
#   –– If N (Not In ER) –– (next_node_id: recent_er_visit_check)

# • Current ER Response (current_node_id: current_er_response)
#   "We're sorry to hear and thanks for sharing. Glad you're seeking care. Please let us know if there's anything we can do for you."
#   (next_node_id: null)

# • Recent ER Visit Check (current_node_id: recent_er_visit_check)
#   "Were you recently discharged from an emergency room visit?"
#   –– If Y (Recent ER Visit) –– (next_node_id: share_er_info)
#   –– If N (No Recent ER Visit) –– (next_node_id: er_recommendation)

# • Share ER Info (current_node_id: share_er_info)
#   "We're sorry to hear about your visit. To help your care team stay in the loop, would you like us to pass on any info? No worries if not, just reply 'no'."
#   (next_node_id: follow_up_support)

# • Follow-Up Support (current_node_id: follow_up_support)
#   "Let us know if you need anything else."
#   (next_node_id: null)

# • ER Recommendation (current_node_id: er_recommendation)
#   "If you're not feeling well or have a medical emergency, go to your local ER. If I misunderstood your message, try rephrasing & using short sentences. You may also reply MENU for a list of support options."
#   (next_node_id: null)

# Evaluation Surveys

# • Pre-Program Impact Survey (current_node_id: pre_program_impact_survey)
#   "Hi there, $patient_firstName$. As you start this program, we'd love to hear your thoughts! We're asking a few questions to understand how you're feeling about managing your early pregnancy."
#   (next_node_id: confidence_rating)

# • Confidence Rating (current_node_id: confidence_rating)
#   "On a 0-10 scale, with 10 being extremely confident, how confident do you feel in your ability to navigate your needs related to early pregnancy? Reply with a number 0-10"
#   (next_node_id: knowledge_rating)

# • Knowledge Rating (current_node_id: knowledge_rating)
#   "On a 0-10 scale, with 10 being extremely knowledgeable, how would you rate your knowledge related to early pregnancy? Reply with a number 0-10"
#   (next_node_id: thank_you_message)

# • Thank You Message (current_node_id: thank_you_message)
#   "Thank you for taking the time to answer these questions. We are looking forward to supporting your health journey."
#   (next_node_id: null)

# • Post-Program Impact Survey (current_node_id: post_program_impact_survey)
#   "Hi $patient_firstname$, glad you finished the program! Sharing your thoughts would be a huge help in making the program even better for others."
#   (next_node_id: post_program_confidence_rating)

# • Post-Program Confidence Rating (current_node_id: post_program_confidence_rating)
#   "On a 0-10 scale, with 10 being extremely confident, how confident do you feel in your ability to navigate your needs related to early pregnancy? Reply with a number 0-10"
#   (next_node_id: post_program_knowledge_rating)

# • Post-Program Knowledge Rating (current_node_id: post_program_knowledge_rating)
#   "On a 0-10 scale, with 10 being extremely knowledgeable, how would you rate your knowledge related to early pregnancy? Reply with a number 0-10"
#   (next_node_id: post_program_thank_you)

# • Post-Program Thank You (current_node_id: post_program_thank_you)
#   "Thank you for taking the time to answer these questions. We are looking forward to supporting your health journey."
#   (next_node_id: null)

# • NPS Quantitative Survey (current_node_id: nps_quantitative_survey)
#   "Hi $patient_firstname$, I have two quick questions about using this text messaging service (last time I promise):"
#   (next_node_id: likelihood_to_recommend)

# • Likelihood to Recommend (current_node_id: likelihood_to_recommend)
#   "On a 0-10 scale, with 10 being 'extremely likely,' how likely are you to recommend this text message program to someone with the same (or similar) situation? Reply with a number 0-10"
#   (next_node_id: nps_qualitative_survey)

# • NPS Qualitative Survey (current_node_id: nps_qualitative_survey)
#   "Thanks for your response. What's the reason for your score?"
#   (next_node_id: feedback_acknowledgment)

# • Feedback Acknowledgment (current_node_id: feedback_acknowledgment)
#   "Thanks, your feedback helps us improve future programs."
#   (next_node_id: null)

# Additional Instructions

# • Always-On Q & A ON FIT (current_node_id: always_on_qa_on_fit)
#   # This node should be the primary target for natural language symptom queries (e.g. "i have question regarding symptoms").
#   "Always-On Q & A ON FIT - Symptom Triage (Nausea, Vomiting & Bleeding + Pregnancy Preference)"
#   (next_node_id: symptom_triage)
#   (Comment: This node directs to Symptom-Triage as the starting point for Q&A when a user texts about symptoms without being prompted by the menu.)

# • General Default Response (current_node_id: general_default_response)
#   "OK. We're here to help. If a symptom or concern comes up, let us know by texting a single symptom or topic."
#   # Note: This default node exists alongside 'default_response'. Keeping both as their usage context is not fully defined here.
#   (next_node_id: null)
# """