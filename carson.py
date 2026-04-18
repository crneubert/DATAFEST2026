# --------------------------------------------
# CLEAN ENCOUNTER-LEVEL TABLE FROM AllData
# --------------------------------------------
import duckdb


departments = duckdb.read_csv(
       r"Data/departments.csv",
       auto_detect=True,
   )
duckdb.sql("""
   SELECT *
   FROM departments
   LIMIT 5
   """)


diagnosis = duckdb.read_csv(
       r"Data/diagnosis.csv",
       auto_detect=True,
   )
duckdb.sql("""
       SELECT *
       FROM diagnosis
       LIMIT 5
       """)


encounters = duckdb.read_csv(
       r"Data/encounters.csv",
       auto_detect=True
   )
duckdb.sql("""
       SELECT *
       FROM encounters
       LIMIT 5
       """)


patients = duckdb.read_csv(
       r"Data/patients.csv",
       auto_detect=True
   )
duckdb.sql("""
       SELECT *
       FROM patients
       LIMIT 5
       """)


providers = duckdb.read_csv(
       r"Data/providers.csv",
       auto_detect=True
   )
duckdb.sql("""
       SELECT *
       FROM providers
       LIMIT 5
       """)


social_determinants = duckdb.read_csv(
       r"Data/social_determinants.csv",
       auto_detect=True
   )
duckdb.sql("""
       SELECT *
       FROM social_determinants
       LIMIT 5
       """)
tigercensuscodes = duckdb.read_csv(
       r"Data/tigercensuscodes.csv",
       auto_detect=True
   )
duckdb.sql("""
       SELECT *
       FROM tigercensuscodes
       LIMIT 5
       """)


AllData = duckdb.sql("""
       SELECT *
       FROM encounters e
       LEFT JOIN departments d
       ON e.DepartmentKey = d.DepartmentKey
       LEFT JOIN diagnosis di
       ON e.PrimaryDiagnosisKey = di.DiagnosisKey
       LEFT JOIN patients p
       ON e.PatientDurableKey = p.DurableKey
       LEFT JOIN providers pr
       ON e.PatientDurableKey = pr.DurableKey
       LEFT JOIN social_determinants s
       ON e.EncounterKey = s.EncounterKey
       """)


EncounterLevel = duckdb.sql("""
WITH encounter_level AS (
   SELECT DISTINCT
       EncounterKey,
       PatientDurableKey,
       CAST(Date AS DATE) AS EncounterDate,


       DepartmentKey,
       DepartmentName,


       DiagnosisKey,
       DiagnosisName,
       DiagnosisValue,
       GroupCode,
       GroupName,


       IsEDVisit,
       IsHospitalAdmission,
       IsHospitalOutpatientVisit,
       IsInpatientAdmission,
       IsObservation,
       IsOutpatientFaceToFaceVisit,


       Type,
       VisitType,
       VisitTypeDescription,


       CensusTract,
       FirstRace,
       MaritalStatus,
       MyChartStatus,
       OmbEthnicity,
       OmbRace,
       PatientBirthYearBin,
       SexAssignedAtBirth,
       SexualOrientation,
       SmokingStatus,
       VitalStatus


   FROM AllData
)
SELECT *
FROM encounter_level
""")


# --------------------------------------------
# MAIN JOURNEY TABLE
# --------------------------------------------
JourneyTable = duckdb.sql("""
WITH encounter_level AS (
   SELECT *
   FROM EncounterLevel
),


data_end AS (
   SELECT MAX(EncounterDate) AS DataEndDate
   FROM encounter_level
),


diabetes_outpatient AS (
   SELECT
       *,
       ROW_NUMBER() OVER (
           PARTITION BY PatientDurableKey
           ORDER BY EncounterDate, EncounterKey
       ) AS rn
   FROM encounter_level
   WHERE GroupName = 'Type 2 diabetes mellitus'
     AND IsOutpatientFaceToFaceVisit = 1
),


index_visits AS (
   SELECT
       PatientDurableKey,
       EncounterKey AS IndexEncounterKey,
       EncounterDate AS IndexOutpatientDate,


       DepartmentKey AS IndexDepartmentKey,
       DepartmentName AS IndexDepartmentName,


       DiagnosisKey AS IndexDiagnosisKey,
       DiagnosisName AS IndexDiagnosisName,
       DiagnosisValue AS IndexDiagnosisValue,
       GroupCode AS IndexGroupCode,
       GroupName AS IndexGroupName,


       Type AS IndexEncounterType,
       VisitType AS IndexVisitType,
       VisitTypeDescription AS IndexVisitTypeDescription,


       CensusTract,
       FirstRace,
       MaritalStatus,
       MyChartStatus,
       OmbEthnicity,
       OmbRace,
       PatientBirthYearBin,
       SexAssignedAtBirth,
       SexualOrientation,
       SmokingStatus,
       VitalStatus
   FROM diabetes_outpatient
   WHERE rn = 1
),


next_diabetes_outpatient AS (
   SELECT
       i.PatientDurableKey,
       MIN(e.EncounterDate) AS SecondOutpatientDate
   FROM index_visits i
   JOIN encounter_level e
     ON e.PatientDurableKey = i.PatientDurableKey
    AND e.GroupName = 'Type 2 diabetes mellitus'
    AND e.IsOutpatientFaceToFaceVisit = 1
    AND (
           e.EncounterDate > i.IndexOutpatientDate
           OR (e.EncounterDate = i.IndexOutpatientDate AND e.EncounterKey <> i.IndexEncounterKey)
        )
   GROUP BY i.PatientDurableKey
),


first_ed_after_index AS (
   SELECT
       i.PatientDurableKey,
       MIN(e.EncounterDate) AS FirstEDDate
   FROM index_visits i
   JOIN encounter_level e
     ON e.PatientDurableKey = i.PatientDurableKey
    AND e.IsEDVisit = 1
    AND (
           e.EncounterDate > i.IndexOutpatientDate
           OR (e.EncounterDate = i.IndexOutpatientDate AND e.EncounterKey <> i.IndexEncounterKey)
        )
   GROUP BY i.PatientDurableKey
),


first_inpatient_after_index AS (
   SELECT
       i.PatientDurableKey,
       MIN(e.EncounterDate) AS FirstInpatientDate
   FROM index_visits i
   JOIN encounter_level e
     ON e.PatientDurableKey = i.PatientDurableKey
    AND e.IsInpatientAdmission = 1
    AND (
           e.EncounterDate > i.IndexOutpatientDate
           OR (e.EncounterDate = i.IndexOutpatientDate AND e.EncounterKey <> i.IndexEncounterKey)
        )
   GROUP BY i.PatientDurableKey
)


SELECT
   i.*,
   d.DataEndDate,
   DATEDIFF('day', i.IndexOutpatientDate, d.DataEndDate) AS DaysObservedAfterIndex,


   CASE
       WHEN DATEDIFF('day', i.IndexOutpatientDate, d.DataEndDate) >= 180 THEN 1
       ELSE 0
   END AS CanObserve180Days,


   o.SecondOutpatientDate,
   CASE
       WHEN o.SecondOutpatientDate IS NOT NULL
       THEN DATEDIFF('day', i.IndexOutpatientDate, o.SecondOutpatientDate)
       ELSE NULL
   END AS DaysToSecondOutpatient,


   ed.FirstEDDate,
   CASE
       WHEN ed.FirstEDDate IS NOT NULL
       THEN DATEDIFF('day', i.IndexOutpatientDate, ed.FirstEDDate)
       ELSE NULL
   END AS DaysToFirstED,


   ip.FirstInpatientDate,
   CASE
       WHEN ip.FirstInpatientDate IS NOT NULL
       THEN DATEDIFF('day', i.IndexOutpatientDate, ip.FirstInpatientDate)
       ELSE NULL
   END AS DaysToFirstInpatient,


   CASE
       WHEN ed.FirstEDDate IS NOT NULL
            AND (o.SecondOutpatientDate IS NULL OR ed.FirstEDDate < o.SecondOutpatientDate)
       THEN 1
       ELSE 0
   END AS EDBeforeFollowup,


   CASE
       WHEN ip.FirstInpatientDate IS NOT NULL
            AND (o.SecondOutpatientDate IS NULL OR ip.FirstInpatientDate < o.SecondOutpatientDate)
       THEN 1
       ELSE 0
   END AS InpatientBeforeFollowup,


   CASE
       WHEN DATEDIFF('day', i.IndexOutpatientDate, d.DataEndDate) < 180 THEN NULL
       WHEN o.SecondOutpatientDate IS NULL THEN 1
       WHEN DATEDIFF('day', i.IndexOutpatientDate, o.SecondOutpatientDate) > 180 THEN 1
       ELSE 0
   END AS Broken180_NoTimelyFollowup,


   CASE
       WHEN DATEDIFF('day', i.IndexOutpatientDate, d.DataEndDate) < 180 THEN NULL
       WHEN (
               ed.FirstEDDate IS NOT NULL
               AND DATEDIFF('day', i.IndexOutpatientDate, ed.FirstEDDate) <= 90
               AND (o.SecondOutpatientDate IS NULL OR ed.FirstEDDate < o.SecondOutpatientDate)
            )
            OR (
               ip.FirstInpatientDate IS NOT NULL
               AND DATEDIFF('day', i.IndexOutpatientDate, ip.FirstInpatientDate) <= 90
               AND (o.SecondOutpatientDate IS NULL OR ip.FirstInpatientDate < o.SecondOutpatientDate)
            )
            OR o.SecondOutpatientDate IS NULL
            OR DATEDIFF('day', i.IndexOutpatientDate, o.SecondOutpatientDate) > 180
       THEN 1
       ELSE 0
   END AS BrokenComposite_180_90


FROM index_visits i
CROSS JOIN data_end d
LEFT JOIN next_diabetes_outpatient o
   ON i.PatientDurableKey = o.PatientDurableKey
LEFT JOIN first_ed_after_index ed
   ON i.PatientDurableKey = ed.PatientDurableKey
LEFT JOIN first_inpatient_after_index ip
   ON i.PatientDurableKey = ip.PatientDurableKey
ORDER BY i.IndexOutpatientDate
""")


journey_df = JourneyTable.df()


print(journey_df.head())
print(journey_df.columns)
from pathlib import Path

path = Path("Data")
path.mkdir(exist_ok=True)

journey_df.to_csv(path / "output.csv", index=False)