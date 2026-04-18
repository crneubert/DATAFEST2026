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

con.sql("""
CREATE OR REPLACE TEMP VIEW tigercensuscodes AS
SELECT * FROM read_csv_auto('Data/tigercensuscodes.csv')
""")

# -----------------------------
# merged encounter-level table
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

print("Building patient journey table...")

# -----------------------------
# patient-level diabetes journey table
# one row per patient
# -----------------------------
con.sql("""
CREATE OR REPLACE TEMP VIEW final_df AS
WITH diabetes_patients AS (
    SELECT DISTINCT PatientDurableKey
    FROM AllData
    WHERE GroupName = 'Type 2 diabetes mellitus'
),

encounter_core AS (
    SELECT DISTINCT *
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
)

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
WHERE DATEDIFF('day', i.FirstOutpatientDate, d.DataEndDate) >= 180
""")

print("Building distance features...")

print("Building distance features...")

# -----------------------------
# tiger geography lookup
# robust to 'NA' strings / bad rows
# -----------------------------
con.sql("""
CREATE OR REPLACE TEMP VIEW tiger_blockgroups AS
SELECT
    LPAD(
        REPLACE(REPLACE(TRIM(CAST(GEOID AS VARCHAR)), '.0', ''), ' ', ''),
        12,
        '0'
    ) AS GEOID_STR,
    TRY_CAST(NULLIF(TRIM(CAST(CENTLAT AS VARCHAR)), 'NA') AS DOUBLE) AS CENTLAT_NUM,
    TRY_CAST(NULLIF(TRIM(CAST(CENTLON AS VARCHAR)), 'NA') AS DOUBLE) AS CENTLON_NUM,
    SUBSTR(
        LPAD(
            REPLACE(REPLACE(TRIM(CAST(GEOID AS VARCHAR)), '.0', ''), ' ', ''),
            12,
            '0'
        ),
        1,
        11
    ) AS CensusTract11
FROM tigercensuscodes
WHERE TRY_CAST(NULLIF(TRIM(CAST(CENTLAT AS VARCHAR)), 'NA') AS DOUBLE) IS NOT NULL
  AND TRY_CAST(NULLIF(TRIM(CAST(CENTLON AS VARCHAR)), 'NA') AS DOUBLE) IS NOT NULL
  AND GEOID IS NOT NULL
""")

con.sql("""
CREATE OR REPLACE TEMP VIEW tiger_tract_centroids AS
SELECT
    CensusTract11,
    AVG(CENTLAT_NUM) AS TractCentLat,
    AVG(CENTLON_NUM) AS TractCentLon
FROM tiger_blockgroups
GROUP BY CensusTract11
""")

# -----------------------------
# final df with distance
# -----------------------------
model_df = con.sql("""
WITH patient_home AS (
    SELECT
        GEOID_STR AS CensusBlockGroupFipsCode,
        CENTLAT_NUM AS PatientLat,
        CENTLON_NUM AS PatientLon
    FROM tiger_blockgroups
),

final_with_geo AS (
    SELECT
        f.*,
        ph.PatientLat,
        ph.PatientLon,
        tt.TractCentLat AS DeptLat,
        tt.TractCentLon AS DeptLon
    FROM final_df f
    LEFT JOIN patient_home ph
        ON LPAD(
            REPLACE(REPLACE(TRIM(CAST(f.CensusBlockGroupFipsCode AS VARCHAR)), '.0', ''), ' ', ''),
            12,
            '0'
        ) = ph.CensusBlockGroupFipsCode
    LEFT JOIN tiger_tract_centroids tt
        ON LPAD(
            REPLACE(REPLACE(TRIM(CAST(f.IndexDepartmentCensusTract AS VARCHAR)), '.0', ''), ' ', ''),
            11,
            '0'
        ) = tt.CensusTract11
)

SELECT
    *,
    CASE
        WHEN PatientLat IS NULL OR PatientLon IS NULL OR DeptLat IS NULL OR DeptLon IS NULL
        THEN NULL
        ELSE 3958.756 * 2 * ASIN(
            SQRT(
                POWER(SIN(RADIANS(DeptLat - PatientLat) / 2), 2) +
                COS(RADIANS(PatientLat)) * COS(RADIANS(DeptLat)) *
                POWER(SIN(RADIANS(DeptLon - PatientLon) / 2), 2)
            )
        )
    END AS DistanceMilesToIndexDept
FROM final_with_geo
ORDER BY FirstOutpatientDate, PatientDurableKey
""").df()

print("done")
print(model_df.shape)
print(model_df[["isBroken", "isAcute"]].mean(numeric_only=True))
print(model_df["DistanceMilesToIndexDept"].describe())
print("distance missing rate:", model_df["DistanceMilesToIndexDept"].isna().mean())

model_df.to_csv("output2.csv", index=False)
print("saved output2.csv")
