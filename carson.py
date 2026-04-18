import duckdb
import pandas as pd

con = duckdb.connect()

# -----------------------------
# load raw files
# -----------------------------
con.sql("""
CREATE OR REPLACE TEMP VIEW departments AS
SELECT * FROM read_csv_auto('Data/departments.csv')
""")

con.sql("""
CREATE OR REPLACE TEMP VIEW diagnosis AS
SELECT * FROM read_csv_auto('Data/diagnosis.csv')
""")

con.sql("""
CREATE OR REPLACE TEMP VIEW encounters AS
SELECT * FROM read_csv_auto('Data/encounters.csv')
""")

con.sql("""
CREATE OR REPLACE TEMP VIEW patients AS
SELECT * FROM read_csv_auto('Data/patients.csv')
""")

con.sql("""
CREATE OR REPLACE TEMP VIEW providers AS
SELECT * FROM read_csv_auto('Data/providers.csv')
""")

con.sql("""
CREATE OR REPLACE TEMP VIEW social_determinants AS
SELECT * FROM read_csv_auto('Data/social_determinants.csv')
""")

# -----------------------------
# clean merged table
# NO long SDOH columns here except for separate flag later
# -----------------------------
con.sql("""
CREATE OR REPLACE TEMP VIEW AllData AS
SELECT
    e.EncounterKey,
    e.PatientDurableKey,
    CAST(e.Date AS DATE) AS EncounterDate,

    e.DepartmentKey,
    e.PrimaryDiagnosisKey,

    e.AdmissionSource,
    e.AdmissionType,

    e.IsEDVisit,
    e.IsHospitalAdmission,
    e.IsHospitalOutpatientVisit,
    e.IsInpatientAdmission,
    e.IsObservation,
    e.IsOutpatientFaceToFaceVisit,

    e.VisitType,
    e.VisitTypeDescription,

    d.DepartmentName,
    d.DepartmentType,
    d.DepartmentSpecialty,
    d.City AS DepartmentCity,
    d.County AS DepartmentCounty,
    d.PostalCode AS DepartmentPostalCode,
    d.CensusTract AS DepartmentCensusTract,

    di.DiagnosisName,
    di.DiagnosisValue,
    di.GroupCode,
    di.GroupName,

    p.CensusBlockGroupFipsCode,
    p.FirstRace,
    p.MaritalStatus,
    p.MyChartStatus,
    p.OmbEthnicity,
    p.OmbRace,
    p.PatientBirthYearBin,
    p.SexAssignedAtBirth,
    p.SexualOrientation,
    p.SmokingStatus,
    p.VitalStatus,

    pr.ClinicianTitle,
    pr.PrimaryDepartment,
    pr.PrimarySpecialty,
    pr.OfficeCity,
    pr.OfficePostalCode

FROM encounters e
LEFT JOIN departments d
    ON e.DepartmentKey = d.DepartmentKey
LEFT JOIN diagnosis di
    ON e.PrimaryDiagnosisKey = di.DiagnosisKey
LEFT JOIN patients p
    ON e.PatientDurableKey = p.DurableKey
LEFT JOIN providers pr
    ON e.AttendingProviderDurableKey = pr.DurableKey
""")

print("Running final modeling query...")

query = """
WITH diabetes_patients AS (
    SELECT DISTINCT PatientDurableKey
    FROM AllData
    WHERE GroupName = 'Type 2 diabetes mellitus'
),

encounter_core AS (
    SELECT DISTINCT
        *
    FROM AllData
    WHERE PatientDurableKey IN (SELECT PatientDurableKey FROM diabetes_patients)
),

data_end AS (
    SELECT MAX(EncounterDate) AS DataEndDate
    FROM encounter_core
),

index_candidates AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY PatientDurableKey
            ORDER BY EncounterDate, EncounterKey
        ) AS rn
    FROM encounter_core
    WHERE GroupName = 'Type 2 diabetes mellitus'
      AND IsOutpatientFaceToFaceVisit = 1
),

index_visits AS (
    SELECT
        PatientDurableKey,
        EncounterKey AS IndexEncounterKey,
        EncounterDate AS FirstOutpatientDate,

        EXTRACT(YEAR FROM EncounterDate) AS IndexYear,
        EXTRACT(MONTH FROM EncounterDate) AS IndexMonth,
        EXTRACT(DOW FROM EncounterDate) AS IndexDayOfWeek,

        DepartmentKey AS IndexDepartmentKey,
        DepartmentName AS IndexDepartmentName,
        DepartmentType AS IndexDepartmentType,
        DepartmentSpecialty AS IndexDepartmentSpecialty,
        DepartmentCity AS IndexDepartmentCity,
        DepartmentCounty AS IndexDepartmentCounty,
        DepartmentPostalCode AS IndexDepartmentPostalCode,
        DepartmentCensusTract AS IndexDepartmentCensusTract,

        DiagnosisName AS IndexDiagnosisName,
        DiagnosisValue AS IndexDiagnosisValue,
        GroupCode AS IndexGroupCode,
        GroupName AS IndexGroupName,

        AdmissionSource AS IndexAdmissionSource,
        AdmissionType AS IndexAdmissionType,
        VisitType AS IndexVisitType,
        VisitTypeDescription AS IndexVisitTypeDescription,

        CensusBlockGroupFipsCode,
        FirstRace,
        MaritalStatus,
        MyChartStatus,
        OmbEthnicity,
        OmbRace,
        PatientBirthYearBin,
        SexAssignedAtBirth,
        SexualOrientation,
        SmokingStatus,
        VitalStatus,

        ClinicianTitle,
        PrimaryDepartment,
        PrimarySpecialty,
        OfficeCity,
        OfficePostalCode
    FROM index_candidates
    WHERE rn = 1
),

second_outpatient AS (
    SELECT
        i.PatientDurableKey,
        MIN(e.EncounterDate) AS SecondOutpatientDate
    FROM index_visits i
    JOIN encounter_core e
      ON e.PatientDurableKey = i.PatientDurableKey
     AND e.GroupName = 'Type 2 diabetes mellitus'
     AND e.IsOutpatientFaceToFaceVisit = 1
     AND (
            e.EncounterDate > i.FirstOutpatientDate
            OR (e.EncounterDate = i.FirstOutpatientDate AND e.EncounterKey <> i.IndexEncounterKey)
         )
    GROUP BY i.PatientDurableKey
),

first_ed AS (
    SELECT
        i.PatientDurableKey,
        MIN(e.EncounterDate) AS FirstEDDate
    FROM index_visits i
    JOIN encounter_core e
      ON e.PatientDurableKey = i.PatientDurableKey
     AND e.IsEDVisit = 1
     AND (
            e.EncounterDate > i.FirstOutpatientDate
            OR (e.EncounterDate = i.FirstOutpatientDate AND e.EncounterKey <> i.IndexEncounterKey)
         )
    GROUP BY i.PatientDurableKey
),

first_inpatient AS (
    SELECT
        i.PatientDurableKey,
        MIN(e.EncounterDate) AS FirstInpatientDate
    FROM index_visits i
    JOIN encounter_core e
      ON e.PatientDurableKey = i.PatientDurableKey
     AND e.IsInpatientAdmission = 1
     AND (
            e.EncounterDate > i.FirstOutpatientDate
            OR (e.EncounterDate = i.FirstOutpatientDate AND e.EncounterKey <> i.IndexEncounterKey)
         )
    GROUP BY i.PatientDurableKey
),

prior_util AS (
    SELECT
        i.PatientDurableKey,

        MAX(e.EncounterDate) FILTER (
            WHERE e.EncounterDate < i.FirstOutpatientDate
        ) AS PrevEncounterDate,

        MAX(e.EncounterDate) FILTER (
            WHERE e.GroupName = 'Type 2 diabetes mellitus'
              AND e.EncounterDate < i.FirstOutpatientDate
        ) AS PrevDiabetesEncounterDate,

        COUNT(DISTINCT e.EncounterKey) FILTER (
            WHERE e.EncounterDate < i.FirstOutpatientDate
              AND e.EncounterDate >= i.FirstOutpatientDate - INTERVAL 180 DAY
        ) AS PriorEncounters180,

        COUNT(DISTINCT e.EncounterKey) FILTER (
            WHERE e.IsOutpatientFaceToFaceVisit = 1
              AND e.EncounterDate < i.FirstOutpatientDate
              AND e.EncounterDate >= i.FirstOutpatientDate - INTERVAL 180 DAY
        ) AS PriorOutpatient180,

        COUNT(DISTINCT e.EncounterKey) FILTER (
            WHERE e.IsEDVisit = 1
              AND e.EncounterDate < i.FirstOutpatientDate
              AND e.EncounterDate >= i.FirstOutpatientDate - INTERVAL 180 DAY
        ) AS PriorED180,

        COUNT(DISTINCT e.EncounterKey) FILTER (
            WHERE e.IsInpatientAdmission = 1
              AND e.EncounterDate < i.FirstOutpatientDate
              AND e.EncounterDate >= i.FirstOutpatientDate - INTERVAL 180 DAY
        ) AS PriorInpatient180,

        COUNT(DISTINCT e.EncounterKey) FILTER (
            WHERE e.GroupName = 'Type 2 diabetes mellitus'
              AND e.EncounterDate < i.FirstOutpatientDate
              AND e.EncounterDate >= i.FirstOutpatientDate - INTERVAL 180 DAY
        ) AS PriorDiabetes180,

        COUNT(DISTINCT e.DepartmentKey) FILTER (
            WHERE e.EncounterDate < i.FirstOutpatientDate
              AND e.EncounterDate >= i.FirstOutpatientDate - INTERVAL 180 DAY
        ) AS PriorDistinctDepartments180,

        COUNT(DISTINCT e.EncounterKey) FILTER (
            WHERE e.EncounterDate < i.FirstOutpatientDate
              AND e.EncounterDate >= i.FirstOutpatientDate - INTERVAL 365 DAY
        ) AS PriorEncounters365,

        COUNT(DISTINCT e.EncounterKey) FILTER (
            WHERE e.IsEDVisit = 1
              AND e.EncounterDate < i.FirstOutpatientDate
              AND e.EncounterDate >= i.FirstOutpatientDate - INTERVAL 365 DAY
        ) AS PriorED365,

        COUNT(DISTINCT e.EncounterKey) FILTER (
            WHERE e.IsInpatientAdmission = 1
              AND e.EncounterDate < i.FirstOutpatientDate
              AND e.EncounterDate >= i.FirstOutpatientDate - INTERVAL 365 DAY
        ) AS PriorInpatient365,

        COUNT(DISTINCT e.EncounterKey) FILTER (
            WHERE e.GroupName = 'Type 2 diabetes mellitus'
              AND e.EncounterDate < i.FirstOutpatientDate
              AND e.EncounterDate >= i.FirstOutpatientDate - INTERVAL 365 DAY
        ) AS PriorDiabetes365
    FROM index_visits i
    LEFT JOIN encounter_core e
      ON e.PatientDurableKey = i.PatientDurableKey
    GROUP BY i.PatientDurableKey
),

sdoh_flag AS (
    SELECT
        EncounterKey,
        1 AS HasAnySDOHAtIndex
    FROM social_determinants
    WHERE AnswerText IS NOT NULL
    GROUP BY EncounterKey
),

final_df AS (
    SELECT
        i.*,
        d.DataEndDate,
        DATEDIFF('day', i.FirstOutpatientDate, d.DataEndDate) AS DaysObservedAfterIndex,

        s.SecondOutpatientDate,
        CASE
            WHEN s.SecondOutpatientDate IS NOT NULL
            THEN DATEDIFF('day', i.FirstOutpatientDate, s.SecondOutpatientDate)
            ELSE NULL
        END AS DaysBetweenFirstSecond,

        ed.FirstEDDate,
        CASE
            WHEN ed.FirstEDDate IS NOT NULL
            THEN DATEDIFF('day', i.FirstOutpatientDate, ed.FirstEDDate)
            ELSE NULL
        END AS DaysUntilED,

        ip.FirstInpatientDate,
        CASE
            WHEN ip.FirstInpatientDate IS NOT NULL
            THEN DATEDIFF('day', i.FirstOutpatientDate, ip.FirstInpatientDate)
            ELSE NULL
        END AS DaysUntilInpatient,

        CASE
            WHEN s.SecondOutpatientDate IS NULL THEN 1
            WHEN DATEDIFF('day', i.FirstOutpatientDate, s.SecondOutpatientDate) > 180 THEN 1
            ELSE 0
        END AS isBroken,

        CASE
            WHEN (
                ed.FirstEDDate IS NOT NULL
                AND DATEDIFF('day', i.FirstOutpatientDate, ed.FirstEDDate) <= 90
                AND (s.SecondOutpatientDate IS NULL OR ed.FirstEDDate < s.SecondOutpatientDate)
            )
            OR (
                ip.FirstInpatientDate IS NOT NULL
                AND DATEDIFF('day', i.FirstOutpatientDate, ip.FirstInpatientDate) <= 90
                AND (s.SecondOutpatientDate IS NULL OR ip.FirstInpatientDate < s.SecondOutpatientDate)
            )
            THEN 1
            ELSE 0
        END AS isAcute,

        CASE
            WHEN pu.PrevEncounterDate IS NOT NULL
            THEN DATEDIFF('day', pu.PrevEncounterDate, i.FirstOutpatientDate)
            ELSE NULL
        END AS DaysSincePrevEncounter,

        CASE
            WHEN pu.PrevDiabetesEncounterDate IS NOT NULL
            THEN DATEDIFF('day', pu.PrevDiabetesEncounterDate, i.FirstOutpatientDate)
            ELSE NULL
        END AS DaysSincePrevDiabetesEncounter,

        pu.PriorEncounters180,
        pu.PriorOutpatient180,
        pu.PriorED180,
        pu.PriorInpatient180,
        pu.PriorDiabetes180,
        pu.PriorDistinctDepartments180,
        pu.PriorEncounters365,
        pu.PriorED365,
        pu.PriorInpatient365,
        pu.PriorDiabetes365,

        COALESCE(sf.HasAnySDOHAtIndex, 0) AS HasAnySDOHAtIndex

    FROM index_visits i
    CROSS JOIN data_end d
    LEFT JOIN second_outpatient s
        ON i.PatientDurableKey = s.PatientDurableKey
    LEFT JOIN first_ed ed
        ON i.PatientDurableKey = ed.PatientDurableKey
    LEFT JOIN first_inpatient ip
        ON i.PatientDurableKey = ip.PatientDurableKey
    LEFT JOIN prior_util pu
        ON i.PatientDurableKey = pu.PatientDurableKey
    LEFT JOIN sdoh_flag sf
        ON i.IndexEncounterKey = sf.EncounterKey
)

SELECT *
FROM final_df
WHERE DaysObservedAfterIndex >= 180
ORDER BY FirstOutpatientDate, PatientDurableKey
"""

model_df = con.sql(query).df()

print("done")
print(model_df.shape)
print(model_df[["isBroken", "isAcute"]].mean(numeric_only=True))

# optional export
model_df.to_csv("output2.csv", index=False)
print("saved output2.csv")