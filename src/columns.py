"""Step 2: the columns this project uses, with plain-language descriptions.

This module is the single source of truth. The join, cleaning, and modeling
scripts import these dictionaries, and `02_columns.py` renders them into
reports/02_column_selection.md, so code and documentation cannot drift apart.

Column groups requested in the brief: first-gen completion, Pell share,
selectivity, size, spending per student. Extra context columns are marked.
"""

# ---------------------------------------------------------------- Scorecard
# Source: College Scorecard, Most-Recent-Cohorts-Institution.csv (one row per campus).
# Strings "NULL" and "PrivacySuppressed" mark missing / small-cell-suppressed values.
SCORECARD = {
    # keys and identity
    "UNITID": "IPEDS unit ID. Primary join key across all files.",
    "OPEID6": "6-digit Office of Postsecondary Education ID. Used to link Opportunity Insights, which is keyed on OPEID.",
    "INSTNM": "Institution name.",
    "STABBR": "State abbreviation.",
    "CONTROL": "Control: 1 = public, 2 = private nonprofit, 3 = private for-profit.",
    "PREDDEG": "Predominant degree awarded: 3 = bachelor's. Used with IPEDS ICLEVEL to define '4-year schools'.",
    "HIGHDEG": "Highest degree awarded (0-4).",
    "MAIN": "1 if this row is the main campus.",
    "CURROPER": "1 if currently operating.",
    "DISTANCEONLY": "1 if the school is distance-education only.",
    "HBCU": "1 if a Historically Black College or University.",
    "LOCALE": "Urban-centric locale code (11 = large city ... 43 = remote rural).",
    "CCBASIC": "Carnegie basic classification code.",
    # OUTCOME: first-generation completion
    "FIRSTGEN_COMP_ORIG_YR6_RT": "OUTCOME. Share of first-generation federal-aid students who completed a credential at this same institution within 6 years of entry.",
    "FIRSTGEN_COMP_4YR_TRANS_YR6_RT": "Context. Share of first-gen students who transferred and completed at a different 4-year school within 6 years.",
    "FIRSTGEN_YR6_N": "Number of first-gen students in the 6-year cohort (the denominator of the outcome). Used as a minimum-cohort filter and for weights.",
    "NOT1STGEN_COMP_ORIG_YR6_RT": "Same 6-year completion rate for students who are NOT first-generation. Lets us compute the first-gen gap.",
    "FIRST_GEN": "Share of federal-aid students who are first-generation (neither parent attended college).",
    # PELL SHARE
    "PCTPELL": "PELL SHARE. Share of undergraduates receiving a Pell Grant (a proxy for low-income enrollment).",
    # SELECTIVITY
    "ADM_RATE": "SELECTIVITY. Admission rate = admitted / applied. Missing for open-admission schools; we set those to 1.0 using IPEDS OPENADMP.",
    "SAT_AVG": "Secondary selectivity measure. Average SAT-equivalent score of admitted students. Missing for ~45% of 4-year schools, so used only in a sensitivity check.",
    # SIZE
    "UGDS": "SIZE. Undergraduate degree-seeking enrollment (fall headcount). Entered in logs.",
    "PPTUG_EF": "Share of undergraduates enrolled part-time.",
    # SPENDING (Scorecard's own per-FTE instruction figure, used to cross-check IPEDS)
    "INEXPFTE": "Instructional expenditure per full-time-equivalent student, as published by Scorecard. Cross-check for the IPEDS-derived figure.",
    "TUITFTE": "Net tuition revenue per FTE student.",
    "AVGFACSAL": "Average monthly faculty salary.",
    "PFTFAC": "Share of faculty who are full-time.",
    # other context
    "C150_4": "Overall completion rate within 150% of normal time (6 years) for first-time full-time students.",
    "RET_FT4": "First-year retention rate of full-time students.",
    "UGDS_WHITE": "Share of undergraduates who are White.",
    "UGDS_BLACK": "Share of undergraduates who are Black.",
    "UGDS_HISP": "Share of undergraduates who are Hispanic.",
    "MD_EARN_WNE_P10": "Median earnings of students 10 years after entry (working, not enrolled).",
}

# ------------------------------------------------------------------- IPEDS
# HD2023: institutional characteristics (one row per institution).
IPEDS_HD = {
    "UNITID": "IPEDS unit ID (join key).",
    "INSTNM": "Institution name (IPEDS spelling).",
    "SECTOR": "Sector: 1 = public 4-year+, 2 = private nonprofit 4-year+, 3 = private for-profit 4-year+, 4-9 = 2-year and below.",
    "ICLEVEL": "Level of institution: 1 = four or more years. Together with PREDDEG=3 this defines our 4-year sample.",
    "CONTROL": "1 public, 2 private nonprofit, 3 private for-profit. Decides which finance survey form the school filed.",
    "HLOFFER": "Highest level of offering (5 = bachelor's ... 9 = doctorate).",
    "INSTCAT": "Institutional category (2 = degree-granting, primarily baccalaureate or above).",
    "C21BASIC": "Carnegie 2021 basic classification.",
    "INSTSIZE": "Enrollment size category (1 = under 1,000 ... 5 = 20,000+).",
    "HBCU": "1 = HBCU, 2 = not.",
    "LOCALE": "Urban-centric locale code.",
    "OBEREG": "Bureau of Economic Analysis region code.",
    "CYACTIVE": "1 = active in the current year; 3 = closed / combined / out of scope.",
    "PSET4FLG": "1 = Title IV postsecondary institution (eligible for federal aid).",
}

# IC2023: institutional characteristics, admissions section.
IPEDS_IC = {
    "UNITID": "IPEDS unit ID (join key).",
    "OPENADMP": "Open admission policy: 1 = yes (admits all applicants), 2 = no, -2 = not applicable. Used to fill missing ADM_RATE with 1.0.",
}

# F2223_F1A: finance for PUBLIC institutions (GASB accounting), fiscal year 2022-23.
# F2223_F2:  finance for PRIVATE NONPROFIT institutions (FASB accounting).
# The two forms label the same functional expense categories with different codes.
# We harmonize them into the common names on the left. Dollar amounts, whole dollars.
SPENDING_CATEGORIES = {
    #  common name          : (F1A public code, F2 private code, description)
    "exp_instruction":        ("F1C011", "F2E011", "Instruction: faculty salaries and everything tied to teaching courses."),
    "exp_research":           ("F1C021", "F2E021", "Research: sponsored and institutional research activity."),
    "exp_public_service":     ("F1C031", "F2E031", "Public service: extension, community programs, broadcasting."),
    "exp_academic_support":   ("F1C051", "F2E041", "Academic support: libraries, advising, tutoring, academic computing, deans' offices."),
    "exp_student_services":   ("F1C061", "F2E051", "Student services: admissions, registrar, counseling, career services, student activities, financial aid office."),
    "exp_institutional_support": ("F1C071", "F2E061", "Institutional support: executive management, HR, legal, fiscal operations, marketing (overhead)."),
    "exp_scholarships":       ("F1C101", "F2E081", "Scholarships / net grant aid to students recorded as expense (not discounts)."),
    "exp_auxiliary":          ("F1C111", "F2E071", "Auxiliary enterprises: housing, dining, bookstore, athletics that charge fees."),
    "exp_total":              ("F1C191", "F2E131", "Total expenses, all functions."),
}
IPEDS_FINANCE_KEYS = {"UNITID": "IPEDS unit ID (join key)."}

# EFIA2023: 12-month enrollment and full-time-equivalent (FTE) counts, 2022-23.
IPEDS_EFIA = {
    "UNITID": "IPEDS unit ID (join key).",
    "FTEUG": "Reported 12-month full-time-equivalent undergraduate enrollment.",
    "FTEGD": "Reported 12-month FTE graduate enrollment.",
    "FTEDPP": "Reported 12-month FTE doctor's-professional-practice enrollment (med, law, etc.).",
}
# SPENDING PER STUDENT = each exp_* category / (FTEUG + FTEGD + FTEDPP).
# Total FTE is the right denominator because instruction, academic support and
# institutional support serve graduate and undergraduate students alike.

# ---------------------------------------------------- Opportunity Insights
# mrc_table2: Mobility Report Cards, preferred estimates, 1980-82 birth cohorts.
# Keyed on super_opeid (groups of OPEIDs that report jointly). mrc_table11 maps
# super_opeid -> OPEID, which we match to Scorecard OPEID6 to reach UNITID.
OI_TABLE2 = {
    "super_opeid": "Opportunity Insights institution group ID (join key to mrc_table11).",
    "name": "Institution (group) name.",
    "tier": "Selectivity tier code (1 = Ivy Plus ... 12 = less selective, etc.).",
    "tier_name": "Selectivity tier label (Barron's-based).",
    "count": "Average number of students per birth cohort.",
    "par_median": "Median parent household income of students (2015 dollars).",
    "par_q1": "Share of students whose parents were in the bottom income quintile (access).",
    "par_rank": "Mean parent income percentile rank.",
    "k_rank": "Mean child income percentile rank at age ~34.",
    "k_median": "Median child earnings at age ~34.",
    "mr_kq5_pq1": "Mobility rate: share of all students who came from the bottom quintile AND reached the top quintile.",
}
OI_TABLE11 = {
    "super_opeid": "Opportunity Insights group ID.",
    "opeid": "6-digit OPEID (stored without leading zeros) of each member institution.",
}
