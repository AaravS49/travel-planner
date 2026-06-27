import os
import datetime
from dotenv import load_dotenv
import streamlit as st
from google import genai
from prompts import build_trip_context, build_itinerary_prompt, build_refine_prompt

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.5-flash"

st.set_page_config(page_title="Travel Planner", page_icon="✈️", layout="wide")
st.title("✈️ Travel Itinerary Planner")

# --- Sidebar: Trip Configuration ---
with st.sidebar:
    st.header("Trip Details")

    st.subheader("Destinations")
    if "destinations" not in st.session_state:
        st.session_state.destinations = [""]

    for i in range(len(st.session_state.destinations)):
        st.session_state.destinations[i] = st.text_input(
            f"City {i + 1}", value=st.session_state.destinations[i], key=f"dest_{i}"
        )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("+ Add City"):
            st.session_state.destinations.append("")
            st.rerun()
    with col2:
        if st.button("- Remove") and len(st.session_state.destinations) > 1:
            st.session_state.destinations.pop()
            st.rerun()

    st.subheader("Dates")
    start_date = st.date_input("Start date", value=datetime.date.today())
    end_date = st.date_input("End date", value=datetime.date.today() + datetime.timedelta(days=4))

    st.subheader("Group")
    adults = st.number_input("Adults", min_value=1, max_value=20, value=1)
    children = st.number_input("Children", min_value=0, max_value=20, value=0)
    if children > 0:
        children_ages = st.text_input("Children's ages (e.g. 3, 7, 12)")
    else:
        children_ages = ""
    elderly = st.number_input("Elderly travelers", min_value=0, max_value=20, value=0)

    st.subheader("Budget")
    currency = st.selectbox("Currency", ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "INR"])
    budget_min, budget_max = st.slider(
        "Total trip budget range", min_value=0, max_value=20000, value=(1000, 5000), step=100
    )

    st.subheader("Restrictions")
    dietary = st.multiselect(
        "Dietary restrictions",
        ["Vegetarian", "Vegan", "Gluten-free", "Halal", "Kosher", "Nut allergy", "Dairy-free"],
    )
    mobility = st.multiselect(
        "Accessibility needs",
        ["Wheelchair accessible", "Limited walking", "No stairs", "Hearing impaired", "Vision impaired"],
    )
    fitness = st.select_slider(
        "Fitness level",
        options=["Very low", "Low", "Moderate", "High", "Very high"],
        value="Moderate",
    )
    other_restrictions = st.text_input("Other restrictions (e.g. no alcohol, fear of heights)")

    st.subheader("Interests")
    must_dos = st.text_area("Must-see places or activities", height=68, placeholder="e.g. Eiffel Tower, sushi-making class")
    general_interests = st.text_area("General interests", height=68, placeholder="e.g. street food, architecture, nightlife")

    generate = st.button("Generate Itinerary", type="primary", use_container_width=True)

# --- Session state init ---
if "itinerary" not in st.session_state:
    st.session_state.itinerary = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Generate itinerary ---
if generate:
    destinations = [d for d in st.session_state.destinations if d.strip()]
    if not destinations:
        st.warning("Please enter at least one destination.")
    elif end_date <= start_date:
        st.warning("End date must be after start date.")
    else:
        dest_str = " → ".join(destinations)
        trip_context = build_trip_context(
            destinations=destinations,
            start_date=start_date,
            end_date=end_date,
            adults=adults,
            children=children,
            children_ages=children_ages,
            elderly=elderly,
            currency=currency,
            budget_min=budget_min,
            budget_max=budget_max,
            dietary=dietary,
            mobility=mobility,
            fitness=fitness,
            other_restrictions=other_restrictions,
            must_dos=must_dos,
            general_interests=general_interests,
        )
        prompt = build_itinerary_prompt(trip_context, currency, fitness)

        st.session_state.chat_history = []
        placeholder = st.empty()
        full_text = ""
        for chunk in client.models.generate_content_stream(model=MODEL, contents=prompt):
            if chunk.text:
                full_text += chunk.text
                placeholder.markdown(full_text)
        st.session_state.itinerary = full_text
        st.rerun()

# --- Display itinerary ---
if st.session_state.itinerary:
    st.markdown(st.session_state.itinerary)

    st.download_button(
        label="Download as Markdown",
        data=st.session_state.itinerary,
        file_name="itinerary.md",
        mime="text/markdown",
    )

    st.divider()
    st.subheader("Refine your itinerary")
    st.caption("Ask anything — the full itinerary is always sent as context so changes stay consistent.")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("e.g. 'Swap day 2 afternoon for something more relaxing'")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        refine_prompt = build_refine_prompt(
            current_itinerary=st.session_state.itinerary,
            chat_history=st.session_state.chat_history[:-1],
            user_request=user_input,
        )

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_text = ""
            for chunk in client.models.generate_content_stream(model=MODEL, contents=refine_prompt):
                if chunk.text:
                    full_text += chunk.text
                    placeholder.markdown(full_text)

        st.session_state.itinerary = full_text
        st.session_state.chat_history.append({"role": "assistant", "content": user_input})
        st.rerun()
