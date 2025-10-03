import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model

st.title("Timetable Generator (Interactive Input)")

# ------------------- Teacher Input -------------------
st.header("Enter Teachers")
num_teachers = st.number_input("Number of teachers", min_value=1, max_value=20, value=3)
teachers = []
for i in range(num_teachers):
    name = st.text_input(f"Teacher {i+1} Name", key=f"t_name_{i}")
    subjects = st.text_input(f"Subjects handled by {name} (comma separated)", key=f"t_subj_{i}")
    teachers.append({
        "id": i,
        "name": name,
        "subjects": [s.strip() for s in subjects.split(",")] if subjects else []
    })

# ------------------- Subject Input -------------------
st.header("Enter Subjects")
num_subjects = st.number_input("Number of subjects", min_value=1, max_value=20, value=3)
subjects = []
for i in range(num_subjects):
    name = st.text_input(f"Subject {i+1} Name", key=f"s_name_{i}")
    hours = st.number_input(f"Hours per week for {name}", min_value=1, max_value=40, value=5, key=f"s_hours_{i}")
    subjects.append({
        "id": i,
        "name": name,
        "hours": hours
    })

# ------------------- Class Input -------------------
st.header("Enter Classes")
num_classes = st.number_input("Number of classes", min_value=1, max_value=10, value=3)
classes = []
for i in range(num_classes):
    cname = st.text_input(f"Class {i+1} Name", key=f"c_name_{i}")
    classes.append(cname)

# ------------------- Days & Periods -------------------
days = st.multiselect(
    "Select Teaching Days",
    ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
    default=["Monday","Tuesday","Wednesday","Thursday","Friday"]
)
periods_per_day = st.number_input("Number of periods per day", min_value=1, max_value=12, value=6)

# ------------------- Timetable Solver -------------------
def generate_timetable(classes, subjects, teachers, days, periods_per_day):
    model = cp_model.CpModel()
    class_subject = {}
    for c in classes:
        for d in range(len(days)):
            for p in range(periods_per_day):
                class_subject[(c,d,p)] = model.NewIntVar(0, len(subjects)-1, f'{c}_{d}_{p}')

    # subject hour constraints
    for c in classes:
        for subj in subjects:
            subj_id = subj["id"]
            required = subj["hours"]
            indicators = []
            for d in range(len(days)):
                for p in range(periods_per_day):
                    is_subj = model.NewBoolVar(f"is_{c}_{d}_{p}_{subj_id}")
                    model.Add(class_subject[(c,d,p)] == subj_id).OnlyEnforceIf(is_subj)
                    model.Add(class_subject[(c,d,p)] != subj_id).OnlyEnforceIf(is_subj.Not())
                    indicators.append(is_subj)
            model.Add(sum(indicators) == required)

    # teacher clash constraint
    for d in range(len(days)):
        for p in range(periods_per_day):
            for t in teachers:
                t_subj_ids = [s["id"] for s in subjects if s["name"] in t["subjects"]]
                indicators = []
                for c in classes:
                    for subj_id in t_subj_ids:
                        is_subj = model.NewBoolVar(f"t{t['id']}_c{c}_d{d}_p{p}_s{subj_id}")
                        model.Add(class_subject[(c,d,p)] == subj_id).OnlyEnforceIf(is_subj)
                        model.Add(class_subject[(c,d,p)] != subj_id).OnlyEnforceIf(is_subj.Not())
                        indicators.append(is_subj)
                model.Add(sum(indicators) <= 1)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    timetable = []
    if status in [cp_model.FEASIBLE, cp_model.OPTIMAL]:
        for d, day in enumerate(days):
            for p in range(periods_per_day):
                for c in classes:
                    subj_id = solver.Value(class_subject[(c,d,p)])
                    subj_name = subjects[subj_id]["name"]
                    timetable.append({
                        "Day": day,
                        "Period": p+1,
                        "Class": c,
                        "Subject": subj_name
                    })
    else:
        st.error("No feasible timetable found")

    return pd.DataFrame(timetable)

# ------------------- Generate Button -------------------
if st.button("Generate Timetable"):
    df_tt = generate_timetable(classes, subjects, teachers, days, periods_per_day)
    if not df_tt.empty:
        st.dataframe(df_tt)
        csv = df_tt.to_csv(index=False).encode("utf-8")
        st.download_button("Download as CSV", csv, "timetable.csv", "text/csv")

