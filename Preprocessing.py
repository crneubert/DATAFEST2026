import duckdb
import numpy
import pandas
import matplotlib
import matplotlib.pyplot as plt

if __name__ == '__main__':
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

    print(AllData.columns)
    importantColumns = duckdb.sql("""
    SELECT  CensusTract, DepartmentKey, DepartmentName, 
            DiagnosisKey, DiagnosisName, DiagnosisValue, 
            GroupCode, GroupName, AdmissionInstant, 
            AdmissionSource, AdmissionType, DischargeInstant, 
            DischargeProviderDurableKey, EncounterKey, IsEDVisit, Date
            IsHospitalAdmission, IsHospitalOutpatientVisit, IsInpatientAdmission,
            IsObservation, IsOutpatientFaceToFaceVisit, PatientDurableKey,
            Type, VisitType, VisitTypeDescription, 
            FirstRace, MaritalStatus, MyChartStatus,
            OmbEthnicity, OmbRace, PatientBirthYearBin,
            SexAssignedAtBirth, SexualOrientation, SmokingStatus,
            VitalStatus, ClinicianTitle, PrimaryDepartment,
            PrimarySpecialty, Type, AnswerText, DisplayName,
            Domain
    FROM AllData
    """)

    # duckdb.sql("""
    # SELECT
    # AVG(IsHospitalAdmission) AS admission_rate
    # FROM AllData
    # WHERE GroupName = 'Type 2 diabetes mellitus';
    # """).show()

    encounters = duckdb.sql("""
    SELECT PatientDurableKey, COUNT(*) AS Encounters, MIN(Date) AS FirstVisit, MAX(Date) AS LastVisit,
    ARRAY_AGG(date ORDER BY date) AS all_dates
    FROM AllData
    WHERE GroupName IN ['Type 2 diabetes mellitus']
    GROUP BY PatientDurableKey
    """)

    AdmittedEncounters = duckdb.sql("""
    SELECT PatientDurableKey, COUNT(*) AS Encounters, MIN(Date) AS FirstVisit, MAX(Date) AS LastVisit,
    ARRAY_AGG(date ORDER BY date) AS all_dates
    FROM AllData
    WHERE GroupName IN ['Type 2 diabetes mellitus']
    AND IsHospitalAdmission = 1
    GROUP BY PatientDurableKey
    """)
    AdmittedEncounters.show()

    #encounters.show()

    encounters2 = duckdb.sql("""
    SELECT *,
    CASE 
           WHEN Encounters > 1
           THEN DATEDIFF('day', all_dates[1], all_dates[2])
           ELSE NULL
       END AS DaysBetweenFirstSecond,
    CASE 
           WHEN Encounters > 1
           THEN DATEDIFF('day', FirstVisit, LastVisit)/(Encounters-1)
           ELSE NULL
       END AS AvgBetweenEnc
    FROM encounters
    """)
    #encounters2.show()

    duckdb.sql("""
    SELECT * FROM encounters2
    WHERE AvgBetweenEnc > 180
    OR Encounters = 1
    """)

    duckdb.sql("""
    SELECT 
    AVG(AvgBetweenEnc) AS mean_days,
    MEDIAN(AvgBetweenEnc) AS median_days,
    MIN(AvgBetweenEnc) AS min_days,
    MAX(AvgBetweenEnc) AS max_days,
    STDDEV(AvgBetweenEnc) AS std_dev_days
    FROM encounters2;
    """)

    df = duckdb.sql("""
    SELECT AvgBetweenEnc 
    FROM encounters2
    WHERE AvgBetweenEnc IS NOT NULL
    """).df()

    df.hist(bins=25)
    #plt.show()

    df = duckdb.sql("""
        SELECT AvgBetweenEnc 
        FROM encounters2
        WHERE AvgBetweenEnc IS NOT NULL
        """).df()

    #df.hist(bins=25)
    #plt.show()

