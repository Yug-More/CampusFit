
# CampusFit

**San José State University | CS 122 — Advanced Programming with Python**

**Authors:** Yug Amol More and Sean Aminov

## Project Overview

CampusFit is a Python-based web application designed to help students explore and compare colleges based on their personal preferences and goals. The application will use publicly available data from the U.S. Department of Education's College Scorecard to provide information about tuition costs, graduation rates, locations, and student outcomes. Students will be able to search for colleges, filter their options, and compare institutions using different criteria. One of the main features will be a What-If Decision Simulator, which allows users to adjust their priorities and see how their college rankings change. Our goal is to make the college selection process easier to understand by presenting useful information through organized comparisons and visualizations.

## Project Outline

### 1. Interface Plan

We plan to develop the application using Python and Flask, with a web interface that allows students to interact with the collected college data.

The interface will include two main pages:

- **College Explorer:** Allows users to search for colleges, apply filters, and view information about individual institutions.
- **Decision Simulator:** Allows users to adjust factors such as affordability, graduation rates, and potential earnings to generate personalized college comparisons.

We also plan to include search fields, dropdown menus, sliders, buttons, and other interactive elements to make the application easy to navigate.

### 2. Data Collection and Storage Plan
**Responsible: Yug Amol More (Author #1)**

- Retrieve publicly available college information using the U.S. Department of Education's College Scorecard API.
- Collect relevant data, including institution names, locations, tuition costs, graduation rates, and available earnings information.
- Use Python to retrieve and organize the data into a consistent structure.
- Handle missing or incomplete values to keep the information suitable for comparisons.
- Store the collected data locally in CSV or JSON format for use throughout the application.
- Make the organized data accessible to the College Explorer and Decision Simulator pages.

### 3. Data Analysis and Visualization Plan
**Responsible: Sean Aminov (Author #2)**

*To be completed by Sean Aminov.*

## Technologies

The following technologies are planned for the project:

- **Python:** Data collection, processing, and application logic
- **Flask:** Web application and user interface
- **Pandas:** Data organization and manipulation
- **NumPy:** Numerical calculations and data analysis
- **Matplotlib:** Data visualization
- **CSV / JSON:** Local data storage
- **College Scorecard API:** Publicly available college information
