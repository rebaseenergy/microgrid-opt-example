import pandas as pd
import matplotlib.pyplot as plt
from model import microgrid_model, microgrid_data_input, solve_model, microgrid_results, microgrid_results_analysis


# Import data
df = pd.read_csv('input.csv', header = 0, sep=',', parse_dates = True, index_col = [0]) 

# Make time series plots
plt.plot(df['pv_power_kW'],color = 'green')
plt.xticks(rotation = 45)
plt.ylabel('Power [kW]')
plt.title('PV generation [kW]')
plt.grid()
plt.show() 


plt.plot(df['load_power_kW'],color = 'red')
plt.xticks(rotation = 45)
plt.ylabel('Load [kW]')
plt.title('Load [kW]')
plt.grid()
plt.show() 



# Set electicity prices
df['price_buy_euros_kWh'] = 0.240382 #€/kWh
df['price_sell_euros_kWh'] = 0.141895 #€/kWh



# Simulation data
data = {'generation': df['pv_power_kW'].to_list(),                  \
        'demand': df['load_power_kW'].to_list(),                    \
        'battery_min_level': 0.1,                                   \
        'battery_capacity': 100,                                    \
        'battery_charge_max': 50,                                   \
        'battery_discharge_max': 50,                                \
        'battery_efficiency_charge': 0.9,                           \
        'battery_efficiency_discharge': 0.9,                        \
        'bel_ini_level': 0.5,                                       \
        'bel_fin_level': 0.5,                                       \
        'energy_price_buy': df['price_buy_euros_kWh'].to_list(),    \
        'energy_price_sell': df['price_sell_euros_kWh'].to_list(),  \
        'grid_fee_energy': 0.05,                                    \
        'grid_fee_power': 10,                                       \
        'grid_overcharge_penalty': 20,                              \
        'grid_power_contract': 0,                                   \
        'dt': 0.25,                                                 \
}
    
    
# Create model data structure
model_data = microgrid_data_input(data) 


# Create model instance with data
model_instance = microgrid_model(model_data)

# Solve
solver = {'name':"glpk",'path': "C:/glpk-4.65/w64/glpsol"}
solution = solve_model(model_instance, solver) 

# Results --> Dictionary
s = microgrid_results(solution)

# Results analysis
r = microgrid_results_analysis(s)




# Make plots
df['battery_soc'] = s['battery_soc']
df['battery_charge'] = s['battery_charge']
df['battery_discharge'] = s['battery_discharge']

df['power_sell'] = s['power_sell']
df['power_buy'] = s['power_buy']

df['cost_energy'] = s['cost_energy']
df['grid_fee_energy'] = s['cost_grid_energy']


# Split battery charge into battery charge from pv and battery charge from grid
df['battery_charge_from_grid'] = df['power_buy'] - df['load_power_kW']
df.loc[(df['power_buy'] - df['load_power_kW']) < 0.00001, 'battery_charge_from_grid'] = 0.0
df['battery_charge_from_pv'] = df['battery_charge'] - df['battery_charge_from_grid']



plt.plot(df['cost_energy'],color = 'gray')
plt.plot(df['grid_fee_energy'],color = 'black')
plt.xticks(rotation = 45)
plt.ylabel('Energy cost [€]')
plt.title('Electricity cost and grid energy fee')
plt.legend(['Electricity cost [€]','Grid energy fee [€]'])
plt.grid()
plt.show()


plt.plot(df['battery_charge'],color = 'red')
plt.plot(-df['battery_discharge'],color = 'green')
plt.xticks(rotation = 45)
plt.ylabel('Battery power [kW]')
plt.title('Battery power')
plt.legend(['Charging [kW]','Discharging [kW]'])
plt.grid()
plt.show()


plt.plot(df['battery_soc'],color = 'green')
plt.xticks(rotation = 45)
plt.ylabel('Battery soc [kWh]')
plt.title('Battery soc')
plt.legend(['Battery soc [kWh]'])
plt.grid()
plt.show()


plt.plot(df['battery_charge_from_pv'],color = 'green')
plt.plot(df['battery_charge_from_grid'],color = 'red')
plt.xticks(rotation = 45)
plt.ylabel('Battery charge [kW]')
plt.title('Battery charge from PV and Grid')
plt.legend(['Charging from PV [kW]','Charging from Grid [kW]'])
plt.grid()
plt.show()


plt.plot(df['power_sell'],color = 'red')
plt.xticks(rotation = 45)
plt.ylabel('Power [kW]')
plt.title('Power sold')
plt.grid()
plt.show()


plt.plot(df['power_buy'],color = 'red')
plt.xticks(rotation = 45)
plt.ylabel('Power [kW]')
plt.title('Power bought')
plt.grid()
plt.show()