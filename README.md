# Type 2 Diabetes Patient Journeys

**DataFest 2026 Finalists | Stormont Vail Hospital**

Our team analyzed patient journeys for people with type 2 diabetes at Stormont Vail Hospital to understand gaps in outpatient follow-up and identify characteristics associated with disrupted care. The project combines SQL data preparation, exploratory analysis, feature engineering, and predictive modeling.

We anchored each journey at the patient's first recorded outpatient diabetes visit. A follow-up gap (`isBroken`) means no subsequent outpatient diabetes visit was recorded within 180 days; index visits had to occur at least 180 days before the dataset ended. We also constructed an indicator for emergency or inpatient care within 90 days, before the next outpatient diabetes visit.

- **Built patient journeys:** Joined encounter, diagnosis, patient, provider, and department data with DuckDB SQL; engineered prior care utilization and approximate distance to the clinic using census geography.
- **Prepared the modeling cohort:** Cleaned a 20,331-row journey table into 18,876 patient records, handling missing values and categorical features.
- **Compared seven classifiers:** Benchmarked elastic-net logistic regression, Random Forest, XGBoost, CatBoost, LightGBM, k-nearest neighbors, and a neural network with five-fold cross-validation and a stratified 80/20 train/test split.
- **Explored interpretation:** Used correlations, mutual information, and logistic-regression coefficients to examine relationships between follow-up gaps, care settings, visit types, and patient characteristics.

In the cleaned cohort, **53.7%** met the follow-up-gap definition. Saved results in [minh.ipynb](minh.ipynb) show **0.728 test ROC AUC for CatBoost**, compared with **0.719 for elastic-net logistic regression**, on 3,776 held-out records. These exploratory results support further investigation of follow-up outreach; an unrecorded visit does not establish that a patient stopped receiving care.

| File | Contents |
| --- | --- |
| [carson.py](carson.py) | Patient journey construction, outcome labels, care history, and distance features |
| [minh.ipynb](minh.ipynb) | Data cleaning, model tuning and comparison, coefficient interpretation |
| [DatafestIan.ipynb](DatafestIan.ipynb) | Random Forest experiments with and without department names |
| [modeling.ipynb](modeling.ipynb) | Exploratory correlations and mutual-information analysis |
| [Preprocessing.py](Preprocessing.py) | Initial SQL exploration of encounters and visit spacing |

**Tools:** Python, SQL/DuckDB, pandas, NumPy, scikit-learn, XGBoost, CatBoost, LightGBM, Matplotlib, seaborn, Jupyter.

Raw source CSVs are not included. Reproducing the full analysis requires the original competition data and adjustments to the notebooks' local file paths.
