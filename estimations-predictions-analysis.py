# -*- coding: utf-8 -*-

"""
Libraries used
"""

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from numpy.linalg import svd
from scipy import stats
from scipy.optimize import minimize, curve_fit
from statsmodels.tsa.arima.model import ARIMA
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from scipy.stats import pearsonr
from statsmodels.stats.stattools import durbin_watson
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.stattools import jarque_bera
import statsmodels.api as sm
import statsmodels.stats.api as sms
from scipy.stats import f_oneway, kstest

"""# I- Estimation et prévision du taux de Mortalité en Nouvelle Zélande avec la méthode de Lee Carter

# a) Estimation du taux de mortalité en Nouvelle Zélande
"""

#Si vous utilisez Google Colab, importez les fichiers excels fournis dans la section fichier du colab

# On charge le fichier Excel
df_lifedeath = pd.read_excel('Life and Death Table NZ.xlsx')

#On nettoie le fichier pour éliminer les plages d'années incomplètes ainsi que les âges trop avancées qui risqueraient de fausser les calculs
df_lifedeath = df_lifedeath[df_lifedeath.Year != 1948]
df_lifedeath = df_lifedeath[df_lifedeath.Year != 1949]
df_lifedeath = df_lifedeath[df_lifedeath.Year != 2022]
df_lifedeath = df_lifedeath[df_lifedeath.Year != 2021]
df_lifedeath = df_lifedeath[df_lifedeath.Year != 2020]
df_lifedeath = df_lifedeath[df_lifedeath.Age != '100-104']
df_lifedeath = df_lifedeath[df_lifedeath.Age != '105-109']
df_lifedeath = df_lifedeath[df_lifedeath.Age != '110+']

df_lifedeath = df_lifedeath.reset_index(drop=True)

# On crée une fonction qui convertit les intervalles pour une meilleure similarité avec l'exemple de l'article 1 pour la méthode de Lee Carter
def convert_to_interval(year):
    lower_bound = year - (year % 5)
    upper_bound = lower_bound + 4
    return f"{lower_bound}-{upper_bound}"

df_lifedeath['Year Interval'] = df_lifedeath['Year'].apply(convert_to_interval)

# On regroupe les données par intervalles d'années et par âge, de plus, on ne selectionne le nombre de mort et d'habitants pour la population générale
aggregated_df = df_lifedeath.groupby(['Year Interval', 'Age']).agg({
    'Total Death': 'sum',
    'Total Population': 'sum'
})

print(aggregated_df)

"""On calcule le taux de mortalité (mortality rate) et le taux de décès (death rate)"""

# On met en forme le dataframe et on extrait le nombre de décès et la population par intervalle d'années
unstacked_df = aggregated_df.unstack(level=1)

total_death_df = unstacked_df['Total Death']

total_population_df = unstacked_df['Total Population']

# On calcule le taux de mortalité
mortality_rate_df = total_death_df / total_population_df

# On calcule le taux de décès
death_rate_df = np.log(1 / (1 - mortality_rate_df))

#Evite que les noms des colonnes soient doublés
mortality_rate_df.columns.name = None
death_rate_df.columns.name = None

#On formatte les dataframes comme dans l'exemple
total_death_df = total_death_df.T
total_population_df = total_population_df.T
mortality_rate_df = mortality_rate_df.T
death_rate_df = death_rate_df.T

total_death_df.index.names = ['Age']
total_population_df.index.names = ['Age']
mortality_rate_df.index.names = ['Age']
death_rate_df.index.names = ['Age']

total_death_df.index = total_death_df.index.str.strip()
total_population_df.index = total_population_df.index.str.strip()
mortality_rate_df.index = mortality_rate_df.index.str.strip()
death_rate_df.index = death_rate_df.index.str.strip()

total_death_df.index = total_death_df.index.fillna('0')
total_population_df.index = total_population_df.index.fillna('0')
mortality_rate_df.index = mortality_rate_df.index.fillna('0')
death_rate_df.index = death_rate_df.index.fillna('0')

age_groups = [
    "0", "01-04", "05-09", "10-14", "15-19", "20-24", "25-29", "30-34",
    "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69",
    "70-74", "75-79", "80-84", "85-89", "90-94", "95-99"
]
time_periods_initial = [
    "1950-1954", "1955-1959", "1960-1964", "1965-1969", "1970-1974",
    "1975-1979", "1980-1984", "1985-1989", "1990-1994", "1995-1999",
    "2000-2004", "2005-2009", "2010-2014", "2015-2019"
]

age_sorting = pd.DataFrame(np.zeros, index=age_groups, columns=time_periods_initial)

# On réorganise les dataframes pour mettre les âges dans l'ordre
total_death_df = total_death_df.reindex(age_sorting.index)
total_population_df = total_population_df.reindex(age_sorting.index)
mortality_rate_df = mortality_rate_df.reindex(age_sorting.index)
death_rate_df = death_rate_df.reindex(age_sorting.index)

#On crée les dataframes pour les calculs avec les données historiques
total_death_df_HD = total_death_df.drop(columns=['2010-2014', '2015-2019'])
total_population_df_HD = total_population_df.drop(columns=[ '2010-2014', '2015-2019'])
mortality_rate_df_HD = mortality_rate_df.drop(columns=[ '2010-2014', '2015-2019'])
death_rate_df_HD = death_rate_df.drop(columns=[ '2010-2014', '2015-2019'])

#On crée le dataframe de comparaison
death_rate_comparison_df = death_rate_df[[ '2010-2014', '2015-2019']]
mortality_rate_comparison_df = mortality_rate_df[[ '2010-2014', '2015-2019']]

print(total_death_df_HD)

print(mortality_rate_df_HD)

print(death_rate_df_HD)

"""On calcule une estimation de ax en suivant la méthode énoncée dans l'article 1"""

ax_df = death_rate_df_HD.apply(lambda row: np.mean(np.log(row)), axis=1)
a_x = ax_df.values

print(ax_df)

"""On calcule une estimation de bx et kt avec SVD comme demandé dans l'article 1"""

# On calcule la matrice résiduelle A_x,t = ln(m_x,t) - ax
A_xt = np.log(death_rate_df_HD) - a_x[:, np.newaxis]

# On effectue la Singular Value Decomposition (SVD)
U, sigma, Vt = svd(A_xt, full_matrices=False)

# On extrait bx et kt
b_x_raw = U[:, 0]  # La première colonne de U
k_t_raw = sigma[0] * Vt[0, :]  # "Première valeur singulière multipliée par la première ligne de Vt

# On s'assure la somme des bx est égale à 1
b_x = b_x_raw / np.sum(b_x_raw)

# On s'assure que la moyenne des kt est égale à 0
k_t = k_t_raw - np.mean(k_t_raw)


# On crée le dataframe pour bx et kt
bx_df = pd.DataFrame({
    'Age Group': death_rate_df_HD.index,
    'b_x': b_x
})


kt_df = pd.DataFrame({
    'Year Group': death_rate_df_HD.columns,
    'k_t': k_t
})


print("b_x DataFrame:")
print(bx_df)

print("\nk_t DataFrame:")
print(kt_df)

"""On optimise k en suivant la méthode de l'article 1


"""

def objective_function(kt, ax, bx, D_xt, E_xt):
    expected_deaths = np.sum(E_xt * np.exp(ax[:, np.newaxis] + bx[:, np.newaxis] * kt), axis=0)
    observed_deaths = np.sum(D_xt, axis=0)
    return np.sum((observed_deaths - expected_deaths)**2)

initial_kt = k_t

result = minimize(objective_function, initial_kt, args=(a_x, b_x, total_death_df_HD, total_population_df_HD))

optimized_kt = result.x

print("k_t optimisé:", optimized_kt)

"""Calcul du taux de mortalité estimé"""

estimated_death_rates = np.exp(a_x[:, np.newaxis] + b_x[:, np.newaxis] * optimized_kt)

time_periods = [
    "1950-1954", "1955-1959", "1960-1964", "1965-1969", "1970-1974",
    "1975-1979", "1980-1984", "1985-1989", "1990-1994", "1995-1999",
    "2000-2004", "2005-2009"
]

estimated_death_rate_df = pd.DataFrame(estimated_death_rates.T, index=time_periods, columns=age_groups)
estimated_death_rate_df = estimated_death_rate_df.T

estimated_mortality_rate_df = 1 - np.exp(-estimated_death_rate_df)
print("Taux de mortalité estimé :")
print(estimated_mortality_rate_df)

"""Calcul du Mean Absolute Deviation (MAD)"""

# Mean Absolute Deviation (MAD) par intervalles d'années
mad_per_year = np.abs(mortality_rate_df_HD.values - estimated_mortality_rate_df.values).mean(axis=1)

# Création d'un dataframe par intervalle d'années
mad_df = pd.DataFrame(mad_per_year, index=death_rate_df_HD.index, columns=["MAD"])

print("Mean Absolute Deviation (MAD) par intervalles d'années :")
print(mad_df)

"""On calcule le  Mean Absolute Percentage Error (MAPE) avec la méthode de l'article 2"""

def calculate_mape(actual_df, forecast_df):
    mape = np.mean(np.abs((actual_df.values - forecast_df.values) / actual_df.values)) * 100
    return mape

def interpret_mape(mape):
    if mape < 10:
        return("Estimation très précise (MAPE < 10%).")
    elif 10 <= mape < 20:
        return("Bonne estimation (10% <= MAPE < 20%).")
    elif 20 <= mape < 50:
        return("Estimation raisonnable (20% <= MAPE < 50%).")
    else:
        return("Estimation peu précise (MAPE >= 50%).")

mape = calculate_mape(mortality_rate_df_HD, estimated_mortality_rate_df)

print(f"MAPE: {mape:.2f}%")
interpret_mape(mape)

"""On calcule MAPE par groupe d'âge pour une analyse plus précise"""

def calculate_mape_per_age_group(actual_df, forecast_df):

    mape_series = np.mean(np.abs((actual_df - forecast_df) / actual_df), axis=1) * 100

    return mape_series

mape_series_classic = calculate_mape_per_age_group(mortality_rate_df_HD, estimated_mortality_rate_df)

for age_group, mape in mape_series_classic.items():
    interpretation = interpret_mape(mape)
    print(f"Age Group: {age_group}, MAPE: {mape:.2f}%, Interpretation: {interpretation}")

def plot_mape_per_age_group(mape_series):

    interpretations = [interpret_mape(mape) for mape in mape_series]

    colors = ['green' if "Estimation très précise (MAPE < 10%)." in interp else
              'yellow' if "Bonne estimation (10% <= MAPE < 20%)." in interp else
              'orange' if "Estimation raisonnable (20% <= MAPE < 50%)." in interp else
              'red' for interp in interpretations]

    plt.figure(figsize=(12, 8))
    plt.bar(mape_series.index, mape_series.values, color=colors)

    plt.title("MAPE par groupe d'âge", fontsize=16)
    plt.xlabel('Age Group', fontsize=14)
    plt.ylabel('MAPE (%)', fontsize=14)
    plt.xticks(rotation=45)
    plt.ylim(0, max(mape_series.values) + 10)

    plt.tight_layout()
    plt.show()

plot_mape_per_age_group(mape_series_classic)

"""Graphs pour comparer le taux de mortalité actuel et estimé pour chaque catégorie"""

actual_color = 'green'
estimated_color = 'blue'

num_age_groups = len(age_groups)

fig, axes = plt.subplots(num_age_groups, 1, figsize=(10, 5 * num_age_groups), sharex=True)

for i, age_group in enumerate(age_groups):
    axes[i].plot(mortality_rate_df_HD.columns, mortality_rate_df_HD.loc[age_group], label='Actual', color=actual_color)
    axes[i].plot(estimated_mortality_rate_df.columns, estimated_mortality_rate_df.loc[age_group], label='Estimate', color=estimated_color)
    axes[i].set_title(f'Group age {age_group}')
    axes[i].set_xlabel('Year')
    axes[i].set_ylabel('Mortality Rate')
    axes[i].legend()

plt.tight_layout()
plt.show()

"""# b) Estimations utilisant la méthode de Lee Carter avec la méthode des Moindres Carrés and Newton Raphson

Utilisons la méthode de Newton Raphson suivant la méthode de l'article pour trouver ax, bx et kt
"""

def lee_carter_newton_raphson(log_m_xt, max_iter=100, tol=1e-6):
    log_m_xt = log_m_xt.values
    n, m = log_m_xt.shape

    ax = np.zeros(n)
    bx = np.ones(n) / n
    kt = np.zeros(m)

    for iteration in range(max_iter):
        ax_old = ax.copy()
        bx_old = bx.copy()
        kt_old = kt.copy()

        for x in range(n):
            sum_term = np.sum(log_m_xt[x, :] - ax_old[x] - bx_old[x] * kt_old)
            ax[x] += sum_term / (m + 1)

        for t in range(m):
            sum_bx_residual = np.sum(bx_old * (log_m_xt[:, t] - ax - bx_old * kt_old[t]))
            sum_bx_squared = np.sum(bx_old ** 2)
            kt[t] += sum_bx_residual / sum_bx_squared

        for x in range(n):
            sum_k_residual = np.sum(kt * (log_m_xt[x, :] - ax[x] - bx_old[x] * kt))
            sum_k_squared = np.sum(kt ** 2)
            bx[x] += sum_k_residual / sum_k_squared

        # On vérifie la convergence
        if (np.max(np.abs(ax - ax_old)) < tol and
            np.max(np.abs(bx - bx_old)) < tol and
            np.max(np.abs(kt - kt_old)) < tol):
            print(f"coverge en {iteration+1} iterations.")
            break
    else:
        print("On a atteint le maximum d'itérations sans que la convergence a été atteinte.")


    a_xNR = ax
    b_xNR = bx
    k_tNR = kt

    return a_xNR, b_xNR, k_tNR

a_x_MCoptimized, b_x_MCoptimized, k_t_MCoptimized = lee_carter_newton_raphson(np.log(death_rate_df_HD))

print("a_x estimé:", a_x_MCoptimized)
print("b_x estimé:", b_x_MCoptimized)
print("k_t estimé:", k_t_MCoptimized)

"""On calcule la Table de mortalité estimée"""

estimated_death_rates_MC = np.exp(a_x_MCoptimized[:, np.newaxis] + b_x_MCoptimized[:, np.newaxis] * k_t_MCoptimized)

age_groups = [
    "0", "01-04", "05-09", "10-14", "15-19", "20-24", "25-29", "30-34",
    "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69",
    "70-74", "75-79", "80-84", "85-89", "90-94", "95-99"
]
time_periods = [
    "1950-1954", "1955-1959", "1960-1964", "1965-1969", "1970-1974",
    "1975-1979", "1980-1984", "1985-1989", "1990-1994", "1995-1999",
    "2000-2004", "2005-2009"
]

estimated_death_rate_MC_df = pd.DataFrame(estimated_death_rates_MC.T, index=time_periods, columns=age_groups)
estimated_death_rate_MC_df = estimated_death_rate_MC_df.T

estimated_mortality_rate_MC_df = 1 - np.exp(-estimated_death_rate_MC_df)

print("Taux de mortalité estimés:")
print(estimated_mortality_rate_MC_df)

"""MAPE Function"""

mape_MC= calculate_mape(mortality_rate_df_HD, estimated_mortality_rate_MC_df)

print(f"MAPE: {mape_MC:.2f}%")

interpret_mape(mape_MC)

mape_series_MC = calculate_mape_per_age_group(mortality_rate_df_HD, estimated_mortality_rate_MC_df)

for age_group, mape in mape_series_MC.items():
    interpretation = interpret_mape(mape)
    print(f"Age du Groupe: {age_group}, MAPE: {mape:.2f}%, Interprétation: {interpretation}")

plot_mape_per_age_group(mape_series_MC)

"""Graphs to compare estimation and calculations"""

actual_color = 'green'
estimated_color = 'blue'

num_age_groups = len(age_groups)

fig, axes = plt.subplots(num_age_groups, 1, figsize=(10, 5 * num_age_groups), sharex=True)

for i, age_group in enumerate(age_groups):
    axes[i].plot(mortality_rate_df_HD.columns, mortality_rate_df_HD.loc[age_group], label='Actual', color=actual_color)
    axes[i].plot(estimated_mortality_rate_MC_df.columns, estimated_mortality_rate_MC_df.loc[age_group], label='Estimate', color=estimated_color)
    axes[i].set_title(f'Age du groupe {age_group}')
    axes[i].set_xlabel('Année')
    axes[i].set_ylabel('Taux de mortalité')
    axes[i].legend()


plt.tight_layout()
plt.show()

"""# c) Predictions utilisant la méthode de Lee Carter avec la régression linéaire

On choisit la deuxième méthode car elle est plus fiable
"""

def create_sequential_time_variable(time_periods):
    return np.arange(len(time_periods)).reshape(-1, 1)


def linear_regression(kt, time_periods, periods_to_forecast=2):

    t = create_sequential_time_variable(time_periods)

    #On applique la régression linéaire
    model = LinearRegression()
    model.fit(t, kt)

    # Forecast future periods based on the sequential index
    t_future = np.arange(len(time_periods), len(time_periods) + periods_to_forecast).reshape(-1, 1)
    RL_prevision_kt = model.predict(t_future)

    alpha = model.intercept_
    beta = model.coef_[0]

    return RL_prevision_kt, alpha, beta

# On prédit les deux périodes de temps suivante avec la régression linéaire
RL_prevision_kt, alpha, beta = linear_regression(k_t_MCoptimized, time_periods, periods_to_forecast=2)

print("kt pour les 2 prochaines périodes prévisionnel:", RL_prevision_kt)
print(f"alpha estimé (intercept): {alpha:.3f}")
print(f"beta estimé (slope): {beta:.3f}")

"""On effectue les tests pour la régression linéaire


"""

t = create_sequential_time_variable(time_periods)

model = LinearRegression()
model.fit(t, k_t_MCoptimized)


predictions = model.predict(t)
residuals = k_t_MCoptimized - predictions

# Correlation (r), Coefficient de Determination (r²), et Durbin-Watson Test
r_squared = model.score(t, k_t_MCoptimized)
correlation = np.corrcoef(k_t_MCoptimized, t.flatten())[0, 1]
dw_statistic = durbin_watson(residuals)

print("R-squared:", r_squared)
print("Correlation (r):", correlation)
print("Durbin-Watson statistic:", dw_statistic)

X = sm.add_constant(t)
ols_model = sm.OLS(k_t_MCoptimized, X).fit()

# F-Test
f_value, p_value_f_test = ols_model.fvalue, ols_model.f_pvalue
print("F-statistic:", f_value, "p-value du F-test:", p_value_f_test)

# Kolmogorov-Smirnov
ks_statistic, p_value_ks = kstest(residuals, 'norm', args=(np.mean(residuals), np.std(residuals)))
print("KS-statistic:", ks_statistic, "p-value de KS :", p_value_ks)

# Test de Glejser Test
_, p_value_glejser, _, _ = sms.het_breuschpagan(residuals, X)
print("p-value du test de Glejser (Breusch-Pagan):", p_value_glejser)

def Prediction_death_rates(ax, bx, forecasted_kt, age_groups, prediction_periods):
    forecast_df = pd.DataFrame(index=age_groups, columns=prediction_periods)

    for i, period in enumerate(prediction_periods):
        forecasted_death_rates = np.exp(ax + bx * forecasted_kt[i])
        forecast_df[period] = forecasted_death_rates

    return forecast_df

prediction_periods = [ '2010-2014', '2015-2019']

Prediction_RL_death_rates_df = Prediction_death_rates(a_x_MCoptimized, b_x_MCoptimized, RL_prevision_kt, age_groups, prediction_periods)

Prediction_RL_mortality_rates_df = 1 - np.exp(-Prediction_RL_death_rates_df)

print(Prediction_RL_mortality_rates_df)

mape_RL = calculate_mape(mortality_rate_comparison_df, Prediction_RL_mortality_rates_df)

print(f"MAPE: {mape_RL:.2f}%")
interpret_mape(mape_RL)

mape_series_RL = calculate_mape_per_age_group(mortality_rate_comparison_df, Prediction_RL_mortality_rates_df)

for age_group, mape in mape_series_RL.items():
    interpretation = interpret_mape(mape)
    print(f"Age du groupe: {age_group}, MAPE: {mape:.2f}%, Interprétation: {interpretation}")

plot_mape_per_age_group(mape_series_RL)

def plot_death_rates_comparison(actual_df, forecast_df, title="Comparaison entre le taux de mortalité prédit et le taux actuel"):
    age_groups = actual_df.index

    plt.figure(figsize=(10, 6))

    plt.plot(age_groups, actual_df.values, label='Actuel', marker='o', color='blue')

    plt.plot(age_groups, forecast_df.values, label='Prévisionnel', marker='o', color='orange')

    plt.title(title)
    plt.xlabel('Age du groupe')
    plt.ylabel('Taux de mortalité')

    plt.xticks(rotation=45)

    plt.legend()

    plt.tight_layout()
    plt.show()

plot_death_rates_comparison(mortality_rate_comparison_df, Prediction_RL_mortality_rates_df, title="Comparaison entre le taux de mortalité prédit par régression linéaire et le taux actuel (2010-2019)")

"""# d) Prédictions utilisant la méthode de Lee Carter avec ARIMA"""

def prediction_kt_Arima(kt, periods=2, arima_order=(0, 1, 0)):

    model = ARIMA(kt, order=arima_order)
    model_fit = model.fit()

    forecast = model_fit.forecast(steps=periods)

    return forecast

ARIMA_kt = prediction_kt_Arima(k_t_MCoptimized, periods=2, arima_order=(0, 1, 0))

print("kt prévisionel pour les 2 prochaines périodes:", ARIMA_kt)

Prediction_ARIMA_death_rates_df = Prediction_death_rates(a_x_MCoptimized, b_x_MCoptimized, ARIMA_kt, age_groups, prediction_periods)

Prediction_ARIMA_mortality_rates_df = 1 - np.exp(-Prediction_ARIMA_death_rates_df)

print(Prediction_ARIMA_mortality_rates_df)

mape_ARIMA = calculate_mape(mortality_rate_comparison_df, Prediction_ARIMA_mortality_rates_df)

print(f"MAPE: {mape_ARIMA:.2f}%")

interpret_mape(mape_ARIMA)

mape_series_ARIMA = calculate_mape_per_age_group(mortality_rate_comparison_df, Prediction_ARIMA_mortality_rates_df)

for age_group, mape in mape_series_ARIMA.items():
    interpretation = interpret_mape(mape)
    print(f"Age du groupe: {age_group}, MAPE: {mape:.2f}%, Interprétation: {interpretation}")

plot_mape_per_age_group(mape_series_ARIMA)

plot_death_rates_comparison(mortality_rate_comparison_df, Prediction_ARIMA_mortality_rates_df, title="Comparaison entre le taux de mortalité prédit avec ARIMA et le taux actuel (2010-2019)")

"""#II- Estimation et prévision du taux de Mortalité de mortalité avec la méthode de Makeham"""

def gompertz_makeham(x, A, B, C):
    return A + B * np.exp(C * x)

age_midpoints = []
for group in age_groups:
    if '-' in group:
        start, end = map(int, group.split('-'))
        midpoint = (start + end) / 2
    else:
        midpoint = int(group)
    age_midpoints.append(midpoint)

age_midpoints = np.array(age_midpoints)

fitted_params = {}
estimated_death_rates_GM_dict = {}

for period in time_periods:

    # On applique le modèle de Gompertz-Makeham au dataset
    popt, pcov = curve_fit(gompertz_makeham, age_midpoints, death_rate_df[period].values, bounds=(0, np.inf))

    A, B, C = popt
    fitted_params[period] = {'A': A, 'B': B, 'C': C}
    print(f"Paramètres ajustés pour {period}: A = {A:.4f}, B = {B:.4f}, C = {C:.4f}")

    estimated_death_rates_GM = gompertz_makeham(age_midpoints, A, B, C)
    estimated_death_rates_GM_dict[period] = estimated_death_rates_GM

    plt.figure(figsize=(10, 6))
    plt.plot(age_midpoints, death_rate_df[period].values, '-', label=f'Taux de mortalité observé ({period})', color='blue')
    plt.plot(age_midpoints, estimated_death_rates_GM, '-', label=f'Gompertz-Makeham Model ajusté ({period})', color='orange')
    plt.xlabel('Age moyen')
    plt.ylabel('Taux de mortalité')
    plt.title(f'Gompertz-Makeham Model adapté à la mortalité par intervalles d age ({period})')
    plt.xticks(age_midpoints, age_groups, rotation=45)
    plt.legend()
    plt.show()

# On extrait le dataset obtenu avec le modèle Gompertz-Makeham
estimated_death_rates_GM_df = pd.DataFrame(estimated_death_rates_GM_dict, index=age_groups)

estimated_mortality_rates_GM_df = 1 - np.exp(-estimated_death_rates_GM_df)

print(estimated_mortality_rates_GM_df)

mape_Makeham = calculate_mape(mortality_rate_df_HD, estimated_mortality_rates_GM_df)

print(f"MAPE: {mape_Makeham:.2f}%")

interpret_mape(mape_Makeham)

mape_series_Makeham = calculate_mape_per_age_group(mortality_rate_df_HD, estimated_mortality_rates_GM_df)

for age_group, mape in mape_series_Makeham.items():
    interpretation = interpret_mape(mape)
    print(f"Age du groupe: {age_group}, MAPE: {mape:.2f}%, Interprétation: {interpretation}")

"""# III- Analyse de l'aspect dynamique de la mortalité

Le modèle retenu est le modèle de Lee-Carter avec pour méthode de prédiction la régression linéaire

On va comparer la mortalité des hommes néo-zélandais à celles des femmes néo-zélandaise pour observer les différences liées au sexe puis celles des populations Maori et non Maori pour observer les différences liées aux critères sociaux économiques. Et par la suite, tester le modèle pour voir si il prend mieux en compte certaines populations que d'autres dans ses prédictions

# a) Comparaison de mortalité entre Hommes et Femmes en Nouvelle Zélande
"""

#Création des dataframes pour les hommes
aggregated_men_df = df_lifedeath.groupby(['Year Interval', 'Age']).agg({
    'Male Death': 'sum',
    'Male Population': 'sum'
})

unstacked_men_df = aggregated_men_df.unstack(level=1)

total_men_death_df = unstacked_men_df['Male Death']

total_men_population_df = unstacked_men_df['Male Population']

mortality_rate_men_df = total_men_death_df / total_men_population_df

death_rate_men_df = np.log(1 / (1 - mortality_rate_men_df))

mortality_rate_men_df.columns.name = None
death_rate_men_df.columns.name = None

total_men_death_df = total_men_death_df.T
total_men_population_df = total_men_population_df.T
mortality_rate_men_df = mortality_rate_men_df.T
death_rate_men_df = death_rate_men_df.T

total_men_death_df.index.names = ['Age']
total_men_population_df.index.names = ['Age']
mortality_rate_men_df.index.names = ['Age']
death_rate_men_df.index.names = ['Age']

total_men_death_df.index = total_men_death_df.index.str.strip()
total_men_population_df.index = total_men_population_df.index.str.strip()
mortality_rate_men_df.index = mortality_rate_men_df.index.str.strip()
death_rate_men_df.index = death_rate_men_df.index.str.strip()

total_men_death_df.index = total_men_death_df.index.fillna('0')
total_men_population_df.index = total_men_population_df.index.fillna('0')
mortality_rate_men_df.index = mortality_rate_men_df.index.fillna('0')
death_rate_men_df.index = death_rate_men_df.index.fillna('0')

total_men_death_df = total_men_death_df.reindex(age_sorting.index)
total_men_population_df = total_men_population_df.reindex(age_sorting.index)
mortality_rate_men_df = mortality_rate_men_df.reindex(age_sorting.index)
death_rate_men_df = death_rate_men_df.reindex(age_sorting.index)

total_men_death_df_HD = total_men_death_df.drop(columns=['2010-2014', '2015-2019'])
total_men_population_df_HD = total_men_population_df.drop(columns=[ '2010-2014', '2015-2019'])
mortality_rate_men_df_HD = mortality_rate_men_df.drop(columns=[ '2010-2014', '2015-2019'])
death_rate_men_df_HD = death_rate_men_df.drop(columns=[ '2010-2014', '2015-2019'])

death_rate_men_comparison_df = death_rate_men_df[[ '2010-2014', '2015-2019']]
mortality_rate_men_comparison_df = mortality_rate_men_df[[ '2010-2014', '2015-2019']]

#Création des dataframes pour les femmes

aggregated_women_df = df_lifedeath.groupby(['Year Interval', 'Age']).agg({
    'Female Death': 'sum',
    'Female Population': 'sum'
})

unstacked_women_df = aggregated_women_df.unstack(level=1)

total_women_death_df = unstacked_women_df['Female Death']

total_women_population_df = unstacked_women_df['Female Population']

mortality_rate_women_df = total_women_death_df / total_women_population_df

death_rate_women_df = np.log(1 / (1 - mortality_rate_women_df))

mortality_rate_women_df.columns.name = None
death_rate_women_df.columns.name = None

total_women_death_df = total_women_death_df.T
total_women_population_df = total_women_population_df.T
mortality_rate_women_df = mortality_rate_women_df.T
death_rate_women_df = death_rate_women_df.T

total_women_death_df.index.names = ['Age']
total_women_population_df.index.names = ['Age']
mortality_rate_women_df.index.names = ['Age']
death_rate_women_df.index.names = ['Age']

total_women_death_df.index = total_women_death_df.index.str.strip()
total_women_population_df.index = total_women_population_df.index.str.strip()
mortality_rate_women_df.index = mortality_rate_women_df.index.str.strip()
death_rate_women_df.index = death_rate_women_df.index.str.strip()

total_women_death_df.index = total_women_death_df.index.fillna('0')
total_women_population_df.index = total_women_population_df.index.fillna('0')
mortality_rate_women_df.index = mortality_rate_women_df.index.fillna('0')
death_rate_women_df.index = death_rate_women_df.index.fillna('0')

total_women_death_df = total_women_death_df.reindex(age_sorting.index)
total_women_population_df = total_women_population_df.reindex(age_sorting.index)
mortality_rate_women_df = mortality_rate_women_df.reindex(age_sorting.index)
death_rate_women_df = death_rate_women_df.reindex(age_sorting.index)

total_women_death_df_HD = total_women_death_df.drop(columns=['2010-2014', '2015-2019'])
total_women_population_df_HD = total_women_population_df.drop(columns=[ '2010-2014', '2015-2019'])
mortality_rate_women_df_HD = mortality_rate_women_df.drop(columns=[ '2010-2014', '2015-2019'])
death_rate_women_df_HD = death_rate_women_df.drop(columns=[ '2010-2014', '2015-2019'])

death_rate_women_comparison_df = death_rate_women_df[[ '2010-2014', '2015-2019']]
mortality_rate_women_comparison_df = mortality_rate_women_df[[ '2010-2014', '2015-2019']]

"""On compare les mportalité par intervalle de temps"""

for period in time_periods:

    plt.figure(figsize=(10, 6))
    plt.plot(age_midpoints, death_rate_men_df_HD[period].values, '-', label=f'Taux de mortalité chez les hommes ({period})', color='blue')
    plt.plot(age_midpoints, death_rate_women_df_HD[period].values, '-', label=f'Taux de mortalité chez les femmes ({period})', color='orange')
    plt.xlabel('Age moyen')
    plt.ylabel('Taux de mortalité')
    plt.title(f'Différences entre hommes et femmes sur le taux de mortalité par intervalles d age ({period})')
    plt.xticks(age_midpoints, age_groups, rotation=45)
    plt.legend()
    plt.show()

"""# b) Testons la précision du modèle retenu sur les deux datasets

On teste le modèle sur la population masculine
"""

a_x_men_MCoptimized, b_x_men_MCoptimized, k_t_men_MCoptimized = lee_carter_newton_raphson(np.log(death_rate_men_df_HD))

print("a_x estimé:", a_x_men_MCoptimized)
print("b_x estimé:", b_x_men_MCoptimized)
print("k_t estimé:", k_t_men_MCoptimized)

# On calcule le taux de décès estimé
estimated_death_rates_men_MC = np.exp(a_x_men_MCoptimized[:, np.newaxis] + b_x_men_MCoptimized[:, np.newaxis] * k_t_men_MCoptimized)

estimated_death_rate_men_MC_df = pd.DataFrame(estimated_death_rates_men_MC.T, index=time_periods, columns=age_groups)
estimated_death_rate_men_MC_df = estimated_death_rate_men_MC_df.T

estimated_mortality_rate_men_MC_df = 1 - np.exp(-estimated_death_rate_men_MC_df)

print("Taux de mortalité estimés:")
print(estimated_death_rate_men_MC_df)

mape_men = calculate_mape(mortality_rate_men_df_HD, estimated_mortality_rate_men_MC_df)

print(f"MAPE: {mape_men:.2f}%")
interpret_mape(mape_men)

RL_prevision_men_kt, alpha_men, beta_men = linear_regression(k_t_men_MCoptimized, time_periods, periods_to_forecast=2)

print("kt estimé pour les deux prochaines périodes:", RL_prevision_men_kt)
print(f"Alpha estimé (intercept): {alpha_men:.3f}")
print(f"Beta estimé (slope): {beta_men:.3f}")

Prediction_RL_death_rates_men_df = Prediction_death_rates(a_x_men_MCoptimized, b_x_men_MCoptimized, RL_prevision_men_kt, age_groups, prediction_periods)

Prediction_RL_mortality_rates_men_df = 1 - np.exp(-Prediction_RL_death_rates_men_df)

print(Prediction_RL_mortality_rates_men_df)

mape_men_prediction = calculate_mape(mortality_rate_men_comparison_df, Prediction_RL_mortality_rates_men_df)

print(f"MAPE: {mape_men_prediction:.2f}%")

interpret_mape(mape_men_prediction)

mape_series_men = calculate_mape_per_age_group(mortality_rate_men_comparison_df, Prediction_RL_mortality_rates_men_df)

for age_group, mape in mape_series_men.items():
    interpretation = interpret_mape(mape)
    print(f"Age du groupe: {age_group}, MAPE: {mape:.2f}%, Interprétation: {interpretation}")

plot_mape_per_age_group(mape_series_men)

"""On teste les modèles retenus chez les femmes"""

a_x_women_MCoptimized, b_x_women_MCoptimized, k_t_women_MCoptimized = lee_carter_newton_raphson(np.log(death_rate_women_df_HD))

print("a_x estimé:", a_x_women_MCoptimized)
print("b_x estimé:", b_x_women_MCoptimized)
print("k_t estimé:", k_t_women_MCoptimized)

# On calcule le taux de décès estimé
estimated_death_rates_women_MC = np.exp(a_x_women_MCoptimized[:, np.newaxis] + b_x_women_MCoptimized[:, np.newaxis] * k_t_women_MCoptimized)

estimated_death_rate_women_MC_df = pd.DataFrame(estimated_death_rates_women_MC.T, index=time_periods, columns=age_groups)
estimated_death_rate_women_MC_df = estimated_death_rate_women_MC_df.T

estimated_mortality_rate_women_MC_df = 1 - np.exp(-estimated_death_rate_women_MC_df)

print("Taux de mortalité estimés:")
print(estimated_mortality_rate_women_MC_df)

mape_women = calculate_mape(mortality_rate_women_df_HD, estimated_mortality_rate_women_MC_df)

print(f"MAPE: {mape_women:.2f}%")
interpret_mape(mape_women)

RL_prevision_women_kt, alpha_women, beta_women = linear_regression(k_t_women_MCoptimized, time_periods, periods_to_forecast=2)

print("kt prévisionnel pour les 2 prochaines périodes:", RL_prevision_women_kt)
print(f"Alpha estimé (intercept): {alpha_women:.3f}")
print(f"Beta estimé (slope): {beta_women:.3f}")

Prediction_RL_death_rates_women_df = Prediction_death_rates(a_x_women_MCoptimized, b_x_women_MCoptimized, RL_prevision_women_kt, age_groups, prediction_periods)

Prediction_RL_mortality_rates_women_df = 1 - np.exp(-Prediction_RL_death_rates_women_df)

print(Prediction_RL_mortality_rates_women_df)

mape_women_prediction = calculate_mape(mortality_rate_women_comparison_df, Prediction_RL_mortality_rates_women_df)

print(f"MAPE: {mape_women_prediction:.2f}%")
interpret_mape(mape_women_prediction)

mape_series_women = calculate_mape_per_age_group(mortality_rate_women_comparison_df, Prediction_RL_mortality_rates_women_df)

for age_group, mape in mape_series_women.items():
    interpretation = interpret_mape(mape)
    print(f"Age du groupe: {age_group}, MAPE: {mape:.2f}%, Interprétation: {interpretation}")

plot_mape_per_age_group(mape_series_women)

"""# c) Comparaison de la mortalité Maori à celle de la population générale

On importe et on met en forme le dataset pour les populations maoris
"""

# Charger le fichier Excel
df_lifedeath_maori = pd.read_excel('Life and Death Table Maori.xlsx')

#On nettoie le fichier pour éliminer les plages d'années incomplètes ainsi que les âges trop avancées qui risqueraient de fausser les calculs
df_lifedeath_maori = df_lifedeath_maori[df_lifedeath_maori.Year != 1948]
df_lifedeath_maori = df_lifedeath_maori[df_lifedeath_maori.Year != 1949]
df_lifedeath_maori = df_lifedeath_maori[df_lifedeath_maori.Age != '100-104']
df_lifedeath_maori = df_lifedeath_maori[df_lifedeath_maori.Age != '105-109']
df_lifedeath_maori = df_lifedeath_maori[df_lifedeath_maori.Age != '110+']

df_lifedeath_maori = df_lifedeath_maori.reset_index(drop=True)

df_lifedeath_maori['Year Interval'] = df_lifedeath_maori['Year'].apply(convert_to_interval)

# On regroupe les données par intervalles d'années et par âge, de plus, on calcul le nombre de mort et d'habitants pour la population générale
aggregated_df_maori = df_lifedeath_maori.groupby(['Year Interval', 'Age']).agg({
    'Total Death': 'sum',
    'Total Population': 'sum'
})

print(aggregated_df_maori)

# On met en forme le dataframe et on extrait le nombre de décès et la population par intervalle d'années
unstacked_df_maori = aggregated_df_maori.unstack(level=1)

total_death_df_maori = unstacked_df_maori['Total Death']

total_population_df_maori = unstacked_df_maori['Total Population']

# On calcule le taux de mortalité
mortality_rate_df_maori = total_death_df_maori / total_population_df_maori

# On calcule le taux de décès
death_rate_df_maori = np.log(1 / (1 - mortality_rate_df_maori))

mortality_rate_df_maori.columns.name = None
death_rate_df_maori.columns.name = None

#On formatte les dataframes comme dans l'exemple
total_death_df_maori = total_death_df_maori.T
total_population_df_maori = total_population_df_maori.T
mortality_rate_df_maori = mortality_rate_df_maori.T
death_rate_df_maori = death_rate_df_maori.T

total_death_df_maori.index.names = ['Age']
total_population_df_maori.index.names = ['Age']
mortality_rate_df_maori.index.names = ['Age']
death_rate_df_maori.index.names = ['Age']

total_death_df_maori.index = total_death_df_maori.index.str.strip()
total_population_df_maori.index = total_population_df_maori.index.str.strip()
mortality_rate_df_maori.index = mortality_rate_df_maori.index.str.strip()
death_rate_df_maori.index = death_rate_df_maori.index.str.strip()

total_death_df_maori.index = total_death_df_maori.index.fillna('0')
total_population_df_maori.index = total_population_df_maori.index.fillna('0')
mortality_rate_df_maori.index = mortality_rate_df_maori.index.fillna('0')
death_rate_df_maori.index = death_rate_df_maori.index.fillna('0')

time_periods_maori = [
    "1950-1954", "1955-1959", "1960-1964", "1965-1969", "1970-1974",
    "1975-1979", "1980-1984", "1985-1989", "1990-1994", "1995-1999"
]


age_sorting = pd.DataFrame(np.zeros, index=age_groups, columns=time_periods)

# On réorganise les dataframes pour mettre les âges dans l'ordre
total_death_df_maori = total_death_df_maori.reindex(age_sorting.index)
total_population_df_maori = total_population_df_maori.reindex(age_sorting.index)
mortality_rate_df_maori = mortality_rate_df_maori.reindex(age_sorting.index)
death_rate_df_maori = death_rate_df_maori.reindex(age_sorting.index)

#On crée les dataframes pour les calculs avec les données historiques
total_death_df_maori_HD = total_death_df_maori.drop(columns=["2000-2004", "2005-2009"])
total_population_df_HD = total_population_df_maori.drop(columns=[ "2000-2004", "2005-2009"])
mortality_rate_maori_df_HD = mortality_rate_df_maori.drop(columns=[ "2000-2004", "2005-2009"])
death_rate_df_maori_HD = death_rate_df_maori.drop(columns=[ "2000-2004", "2005-2009"])

#On crée le dataframe de prédiction
death_rate_comparison_maori_df = death_rate_df_maori[[ "2000-2004", "2005-2009"]]
mortality_rate_comparison_maori_df = mortality_rate_df_maori[[ "2000-2004", "2005-2009"]]

for period in time_periods:

    plt.figure(figsize=(10, 6))
    plt.plot(age_midpoints, mortality_rate_df_HD[period].values, '-', label=f'Taux de mortalité Nouvelle Zélande ({period})', color='blue')
    plt.plot(age_midpoints, mortality_rate_df_maori[period].values, '-', label=f'Taux de mortalité Maori ({period})', color='orange')
    plt.xlabel('Age moyen')
    plt.ylabel('Taux de mortalité')
    plt.title(f'Différences de taux de mortalité par intervalle d age entre Maori et non Maori ({period})')
    plt.xticks(age_midpoints, age_groups, rotation=45)
    plt.legend()
    plt.show()

"""#  d) Testons la précision des modèles d'estimation et de prédictions retenus sur la population Maori"""

a_x_maori_MCoptimized, b_x_maori_MCoptimized, k_t_maori_MCoptimized = lee_carter_newton_raphson(np.log(death_rate_df_maori_HD))

print("a_x estimé:", a_x_maori_MCoptimized)
print("b_x estimé:", b_x_maori_MCoptimized)
print("k_t estimé:", k_t_maori_MCoptimized)

# On calcule le taux de décès estimé
estimated_death_rates_maori_MC = np.exp(a_x_maori_MCoptimized[:, np.newaxis] + b_x_maori_MCoptimized[:, np.newaxis] * k_t_maori_MCoptimized)

estimated_death_rate_maori_MC_df = pd.DataFrame(estimated_death_rates_maori_MC.T, index=time_periods_maori, columns=age_groups)
estimated_death_rate_maori_MC_df = estimated_death_rate_maori_MC_df.T

estimated_mortality_rate_maori_MC_df = 1 - np.exp(-estimated_death_rate_maori_MC_df)

print("Taux de mortalité estimés:")
print(estimated_mortality_rate_maori_MC_df)

mape_maori = calculate_mape(mortality_rate_maori_df_HD, estimated_mortality_rate_maori_MC_df)

print(f"MAPE: {mape_maori:.2f}%")
interpret_mape(mape_maori)

RL_prevision_maori_kt, alpha_maori, beta_maori = linear_regression(k_t_maori_MCoptimized, time_periods_maori, periods_to_forecast=2)

print("kt prévisionnel pour les 2 prochaines périodes:", RL_prevision_maori_kt)
print(f"Alpha estimé (intercept): {alpha_maori:.3f}")
print(f"Beta estimé (slope): {beta_maori:.3f}")

prediction_periods_maori = [ "2000-2004", "2005-2009"]

Prediction_RL_death_rates_maori_df = Prediction_death_rates(a_x_maori_MCoptimized, b_x_maori_MCoptimized, RL_prevision_maori_kt, age_groups, prediction_periods_maori)

Prediction_RL_mortality_rates_maori_df = 1 - np.exp(-Prediction_RL_death_rates_maori_df)

print(Prediction_RL_mortality_rates_maori_df)

mape_maori_prediction = calculate_mape(mortality_rate_comparison_maori_df, Prediction_RL_mortality_rates_maori_df)

print(f"MAPE: {mape_maori_prediction:.2f}%")
interpret_mape(mape_maori_prediction)

mape_series_maori_RL = calculate_mape_per_age_group(mortality_rate_comparison_maori_df, Prediction_RL_mortality_rates_maori_df)

for age_group, mape in mape_series_maori_RL.items():
    interpretation = interpret_mape(mape)
    print(f"Age du groupe: {age_group}, MAPE: {mape:.2f}%, Interprétation: {interpretation}")

plot_mape_per_age_group(mape_series_maori_RL)

"""On va tester avec ARIMA"""

ARIMA_kt_maori = prediction_kt_Arima(k_t_maori_MCoptimized, periods=2, arima_order=(0, 1, 0))

print("kt prévisionnel pour les 2 prochaines périodes:", ARIMA_kt_maori)

Prediction_ARIMA_death_rates_maori_df = Prediction_death_rates(a_x_maori_MCoptimized, b_x_maori_MCoptimized, ARIMA_kt_maori, age_groups, prediction_periods_maori)

Prediction_ARIMA_mortality_rates_maori_df = 1 - np.exp(-Prediction_ARIMA_death_rates_maori_df)

print(Prediction_ARIMA_mortality_rates_maori_df)

mape_maori_ARIMA_prediction = calculate_mape(mortality_rate_comparison_maori_df, Prediction_ARIMA_mortality_rates_maori_df)

print(f"MAPE: {mape_maori_ARIMA_prediction:.2f}%")
interpret_mape(mape_maori_ARIMA_prediction)

mape_series_maori_ARIMA = calculate_mape_per_age_group(mortality_rate_comparison_maori_df, Prediction_ARIMA_mortality_rates_maori_df)

for age_group, mape in mape_series_maori_ARIMA.items():
    interpretation = interpret_mape(mape)
    print(f"Age du groupe: {age_group}, MAPE: {mape:.2f}%, Interprétation: {interpretation}")

plot_mape_per_age_group(mape_series_maori_ARIMA)
