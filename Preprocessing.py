import duckdb
if __name__ == '__main__':
    departments = duckdb.read_csv(
        r"Data/departments.csv",
        auto_detect=True,
    )
    duckdb.sql("""
    SELECT *
    FROM departments
    LIMIT 5
    """).show()

    diagnosis = duckdb.read_csv(
        r"Data/diagnosis.csv",
        auto_detect=True,
    )
    duckdb.sql("""
        SELECT *
        FROM diagnosis
        LIMIT 5
        """).show()

    encounters = duckdb.read_csv(
        r"Data/encounters.csv",
        auto_detect=True
    )
    duckdb.sql("""
        SELECT *
        FROM encounters
        LIMIT 5
        """).show()

    patients = duckdb.read_csv(
        r"Data/patients.csv",
        auto_detect=True
    )
    duckdb.sql("""
        SELECT *
        FROM patients
        LIMIT 5
        """).show()

    providers = duckdb.read_csv(
        r"Data/providers.csv",
        auto_detect=True
    )
    duckdb.sql("""
        SELECT *
        FROM providers
        LIMIT 5
        """).show()

    social_determinants = duckdb.read_csv(
        r"Data/social_determinants.csv",
        auto_detect=True
    )
    duckdb.sql("""
        SELECT *
        FROM social_determinants
        LIMIT 5
        """).show()

    tigercensuscodes = duckdb.read_csv(
        r"Data/tigercensuscodes.csv",
        auto_detect=True
    )
    duckdb.sql("""
        SELECT *
        FROM tigercensuscodes
        LIMIT 5
        """).show()

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
    AllData.show()