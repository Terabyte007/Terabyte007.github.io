# 🎓 Gender vs Academic Performance Analysis

This project explores whether there is a significant difference in academic performance between **male and female students**, using a simulated dataset of over 60,000 student records.

---

## 📚 Table of Contents

- [🎯 Business Understanding](#-business-understanding)
- [📊 Data Understanding](#-data-understanding)
- [📁 Project Structure](#-project-structure)
- [🔍 Approach](#-approach)
- [📈 Screenshots of Visualizations/Results](#-screenshots-of-visualizationsresults)
- [🛠 Technologies](#-technologies)
- [⚙️ Setup](#️-setup)
- [📌 Status](#-status)
- [🙏 Credits](#-credits)
- [🙋‍♂️ About Me](#️-about-me)

---

## 🎯 Business Understanding

This project investigates a commonly debated question:  
> *Which gender performs better academically — male or female?*

The goal is to:
- Understand the distribution and performance of each gender
- Determine if there is a **statistically significant** difference in CGPA
- Gain insight into possible contributing factors (UTME, WAEC)

**Why this project?**  
Gender-related performance trends are often generalized. This analysis takes a **data-driven approach** to challenge or support those assumptions.

**Challenges encountered:**
- Data inconsistencies (e.g. messy gender entries)
- Missing and outlier values in CGPA
- Balancing interpretability with statistical rigor

---

## 📊 Data Understanding

The dataset was **synthetically generated** to reflect realistic patterns and problems in educational records. It contains 60,000+ entries with the following fields:

| Column         | Description                            |
|----------------|----------------------------------------|
| `student_id`   | Unique ID for each student             |
| `gender`       | Gender (e.g., "M", "female", "Woman")  |
| `cgpa`         | Final academic score (0.00–5.00 scale) |
| `waec_score`   | WAEC examination result                |
| `utme_score`   | UTME examination score                 |
| `department`   | Department of study                    |
| `level`        | Academic level (100–500)               |

**Future Enhancements:**
- Include attendance records or behavioral metrics
- Compare with real institutional data (if available)
- Analyze longitudinal trends over time
- Add predictive model: *Can we predict CGPA from WAEC & UTME scores?*
- Interactive dashboard with Plotly or Streamlit
- Benchmark against real anonymized datasets (if available)

---

## 📁 Project Structure

```
gender-performance-analysis/
│
├── data/
│   └── student_performance.csv       # Simulated raw data
│
├── notebooks/
│   └── gender_analysis.ipynb         # Jupyter Notebook (EDA + Stats)
│
├── output/
│   └── visualizations/               # Saved plots and charts
│
├── report.md                         # Written analysis summary
└── README.md                         # Project overview (this file)
```

---

## 🔍 Approach

### 1. Data Cleaning
- Normalized gender entries into `"Male"` and `"Female"`
- Removed or imputed missing CGPA values
- Filtered or flagged outliers

### 2. Exploratory Data Analysis (EDA)
- Gender count and CGPA distribution
- Visualizations: histogram, boxplot, violin plot
- Correlation between CGPA and WAEC/UTME

### 3. Statistical Testing
- Independent t-test to compare CGPA between genders
- Normality and variance checks to validate assumptions

### 4. Reporting
- Summary of findings
- Visual storytelling
- Final recommendation

---

## 📈 Screenshots of Visualizations/Results

_Examples of generated outputs:_

<p align="center">
  <img src="output/visualizations/boxplot_gender_cgpa.png" width="400">
  <br><em>Figure: Boxplot of CGPA by Gender</em>
</p>

<p align="center">
  <img src="output/visualizations/hist_cgpa_distribution.png" width="400">
  <br><em>Figure: Histogram of CGPA Distribution</em>
</p>

---

## 🛠 Technologies

This project was built using:

- Python 🐍
  - `pandas` for data manipulation
  - `numpy` for numerical analysis
  - `seaborn` & `matplotlib` for visualization
  - `scipy.stats` for statistical testing
- Jupyter Notebook
- Git & GitHub for version control
- Markdown for documentation

---

## ⚙️ Setup

To run this project locally:

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/gender-performance-analysis.git
   cd gender-performance-analysis
   ```

2. Install dependencies:
   ```bash
   pip install pandas numpy seaborn matplotlib scipy
   ```

3. Open the notebook:
   ```bash
   jupyter notebook notebooks/gender_analysis.ipynb
   ```

Make sure the `data/student_performance.csv` file is in place.

---

## 📌 Status

🚧 **In Process**  
- EDA and statistical testing complete  
- Report and polishing in progress  
- To be deployed as an interactive dashboard (future milestone)

Version: `v1.0`

---

## 🙏 Credits

Special thanks to:
- The [OpenAI ChatGPT](https://openai.com/chatgpt) team for assisting in structuring the project
- Public data standards from academic institutions for real-world reference

---

## 🙋‍♂️ About Me

Hi, I’m **Afeez Ajadi** – a data analyst passionate about uncovering insights from educational data. I focus on building clean, insightful analytics projects with storytelling at the core.  
Check out more of my work at 👉 [terabyte007.github.io](https://terabyte007.github.io/)

---

> “In God we trust. All others must bring data.” – W. Edwards Deming
> “Good data analysis tells a story. Great data analysis answers a question that matters.”