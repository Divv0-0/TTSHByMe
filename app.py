import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model

st.title("TIMETABLE GENERATOR")

# ------------------- Upload Files -------------------
teachers_file = st.file_uploader("Upload Teachers CSV/XLSX", type=["csv","xlsx"])
subjects_file = st.file_uploader("Upload Subjects CSV/XLSX", type=["csv","xlsx"])
classes_file = st.file_uploader("Upload Classes CSV/XLSX", type=["csv","xlsx"])

def load_file(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    else:
        return pd.read_excel(file)

teachers_df = load_file(teachers_file) if teachers_file else None
subjects_df = load_file(subjects_file) if subjects_file else None
classes_df = load_file(classes_file) if classes_file else None

# ------------------- Column Mapping -------------------
if teachers_df is not None:
    st.subheader("Map Teacher Columns")
    teacher_name_col = st.selectbox("Select Teacher Name column", teachers_df.columns, key="t_name")
    teacher_subjects_col = st.selectbox("Select Subjects Handled column", teachers_df.columns, key="t_subj")
    if st.checkbox("Preview Teachers", key="show_teacher"):
        st.dataframe(teachers_df.head())

if subjects_df is not None:
    st.subheader("Map Subject Columns")
    subject_name_col = st.selectbox("Select Subject Name column", subjects_df.columns, key="s_name")
    subject_hours_col = st.selectbox("Select Subject Hours column", subjects_df.columns, key="s_hours")
    if st.checkbox("Preview Subjects", key="show_subjects"):
        st.dataframe(subjects_df.head())

if classes_df is not None:
    st.subheader("Map Class Column")
    class_col = st.selectbox("Select Class Name column", classes_df.columns, key="c_name")
    if st.checkbox("Preview Classes", key="show_classes"):
        st.dataframe(classes_df.head())

# ------------------- Days & Periods -------------------
days = st.multiselect(
    "Select Teaching Days",
    ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"],
    default=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
)
periods_per_day = st.number_input("Number of periods per day", min_value=1, max_value=12, value=6)

# ------------------- Timetable Generator -------------------
def generate_timetable(classes, subjects, teachers, days, periods_per_day):
    model = cp_model.CpModel()
    class_subject = {}
    for c in classes:
        for d in range(len(days)):
            for p in range(periods_per_day):
                class_subject[(c,d,p)] = model.NewIntVar(0, len(subjects)-1, f'{c}_{d}_{p}')

    # Each subject required hours per class
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

    # Teacher clash prevention
    for d in range(len(days)):
        for p in range(periods_per_day):
            for t in teachers:
                t_subj_ids = t["subjects"]
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
    if teachers_df is None or subjects_df is None or classes_df is None:
        st.error("Upload all three files first!")
    else:
        # Prepare subjects
        subjects = []
        for i, row in subjects_df.iterrows():
            subjects.append({
                "id": i,
                "name": row[subject_name_col],
                "hours": int(row[subject_hours_col])
            })

        # Prepare classes
        classes = classes_df[class_col].tolist()

        # Prepare teachers (map by subject name)
        teachers = []
        for i, row in teachers_df.iterrows():
            handled = [s.strip() for s in row[teacher_subjects_col].split(",")]
            subj_ids = [subj["id"] for subj in subjects if subj["name"] in handled]
            teachers.append({
                "id": i,
                "name": row[teacher_name_col],
                "subjects": subj_ids
            })

        # Validate subjects have teachers
        for subj in subjects:
            if not any(subj["id"] in t["subjects"] for t in teachers):
                st.warning(f"No teacher available for subject: {subj['name']}")

        # Generate timetable
        df_tt = generate_timetable(classes, subjects, teachers, days, periods_per_day)
        st.dataframe(df_tt)

        # Download button
        csv = df_tt.to_csv(index=False).encode("utf-8")
        st.download_button("Download as CSV", csv, "timetable.csv", "text/csv")
