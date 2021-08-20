from pyomo.environ import ConcreteModel
from pyomo.environ import Set,Param,Var,Objective,Constraint
from pyomo.environ import PositiveIntegers, NonNegativeReals, Reals
from pyomo.environ import SolverFactory, minimize
from pyomo.environ import value
from pyomo.core.base.param import SimpleParam
import numpy as np



def solve_model(model_instance):        
    
    optimizer = SolverFactory("glpk", executable="/usr/bin/glpsol")
    optimizer.solve(model_instance, tee=True, keepfiles=True)


    return model_instance



def microgrid_model(model_data):


    model = ConcreteModel()

    ## SETS
    model.T = Set(dimen=1, ordered=True, initialize=model_data[None]['T']) # Periods



    ## PARAMETERS
    model.demand                        = Param(model.T, within=Reals, initialize=model_data[None]['demand'])
    model.generation                    = Param(model.T, initialize=model_data[None]['generation'])

    model.battery_min_level             = Param(initialize=model_data[None]['battery_min_level'])
    model.battery_capacity              = Param(initialize=model_data[None]['battery_capacity'])
    model.battery_charge_max            = Param(initialize=model_data[None]['battery_charge_max'])
    model.battery_discharge_max         = Param(initialize=model_data[None]['battery_discharge_max'])
    model.battery_efficiency_charge     = Param(initialize=model_data[None]['battery_efficiency_charge'])
    model.battery_efficiency_discharge  = Param(initialize=model_data[None]['battery_efficiency_discharge'])
    model.bel_ini_level                 = Param(initialize=model_data[None]['bel_ini_level'])
    model.bel_fin_level                 = Param(initialize=model_data[None]['bel_fin_level'])

    model.energy_price_buy              = Param(model.T, initialize=model_data[None]['energy_price_buy'])
    model.energy_price_sell             = Param(model.T, initialize=model_data[None]['energy_price_sell'])
    model.grid_fee_energy               = Param(initialize=model_data[None]['grid_fee_energy'])
    model.grid_fee_power                = Param(initialize=model_data[None]['grid_fee_power'])
    model.grid_overcharge_penalty       = Param(initialize=model_data[None]['grid_overcharge_penalty'])
    model.grid_power_contract           = Param(initialize=model_data[None]['grid_power_contract'])


    model.dt                            = Param(initialize=model_data[None]['dt'])



    ## VARIABLE LIMITS
    def soc_limits(model, t):
        return (model.battery_min_level*model.battery_capacity, model.battery_capacity)
    def charge_limits(model, t):
        return (0.0, model.battery_charge_max)
    def discharge_limits(model, t):
        return (0.0, model.battery_discharge_max)


    ## VARIABLES
    model.COST_ENERGY       = Var(model.T)
    model.COST_GRID_ENERGY  = Var(model.T)
    model.COST_GRID_POWER   = Var()
    model.P_CONTR           = Var(within=NonNegativeReals)
    model.P_OVER            = Var(within=NonNegativeReals)
    model.P_BUY             = Var(model.T, within=NonNegativeReals)
    model.P_SELL            = Var(model.T, within=NonNegativeReals)
    model.BEL               = Var(model.T, within=NonNegativeReals, bounds=soc_limits)
    model.B_IN              = Var(model.T, within=NonNegativeReals, bounds=charge_limits)
    model.B_OUT             = Var(model.T, within=NonNegativeReals, bounds=discharge_limits)




    ## OBJECTIVE
    # Minimize cost
    def total_cost(model):
        return sum(model.COST_ENERGY[t] + model.COST_GRID_ENERGY[t] for t in model.T) + model.COST_GRID_POWER
    model.total_cost = Objective(rule=total_cost, sense=minimize)




    ## CONSTRAINTS
    # Energy cost
    def energy_cost(model, t):
        return model.COST_ENERGY[t] == model.energy_price_buy[t]*model.P_BUY[t]*model.dt - model.energy_price_sell[t]*model.P_SELL[t]*model.dt
    model.energy_cost = Constraint(model.T, rule=energy_cost)


    # Grid energy cost
    def grid_energy_cost(model, t):
        return model.COST_GRID_ENERGY[t] == model.grid_fee_energy*(model.P_BUY[t]+model.P_SELL[t])*model.dt
    model.grid_energy_cost = Constraint(model.T, rule=grid_energy_cost)

    # Grid power cost
    def grid_power_cost(model):
        return model.COST_GRID_POWER == model.grid_fee_power*model.P_CONTR + model.grid_overcharge_penalty*model.P_OVER
    model.grid_power_cost = Constraint(model.T, rule=grid_power_cost)


    # Overcharge
    def overcharge_import(model, t):
        return model.P_OVER >= model.P_BUY[t] - model.P_CONTR
    model.overcharge_import = Constraint(model.T, rule=overcharge_import)

    def overcharge_export(model, t):
        return model.P_OVER >= model.P_SELL[t] - model.P_CONTR
    model.overcharge_export = Constraint(model.T, rule=overcharge_export)



    # Energy balance
    def energy_balance(model, t):
        return model.P_SELL[t] - model.P_BUY[t] ==  model.generation[t] + model.B_OUT[t] - model.B_IN[t] - model.demand[t]
    model.energy_balance = Constraint(model.T, rule=energy_balance)


    # Battery energy balance
    def battery_soc(model, t):
        if t==model.T.first():
            return model.BEL[t] - model.bel_ini_level*model.battery_capacity == model.battery_efficiency_charge*model.B_IN[t]*model.dt  - (1/model.battery_efficiency_discharge)*model.B_OUT[t]*model.dt
        else:
            return model.BEL[t] - model.BEL[model.T.prev(t)] == model.battery_efficiency_charge*model.B_IN[t]*model.dt  - (1/model.battery_efficiency_discharge)*model.B_OUT[t]*model.dt
    model.battery_soc = Constraint(model.T, rule=battery_soc)

    # Fix battery soc in the last period
    if value(model.bel_fin_level) > 0:
        model.BEL[model.T.last()].fix(model.bel_fin_level*model.battery_capacity)
    
    # Fix power contract (if 0 then power contract level is optimized)
    if value(model.grid_power_contract) > 0:
        model.P_CONTR.fix(model.grid_power_contract)

    return model


def microgrid_data_input(data):


    # data = {'generation': [10.5, 12.3, 11.3, 14.7, 15.1, 14.2],     \
    #         'demand': [8.5, 6.3, 15.3, 18.7, 17.1, 11.2],           \
    #         'battery_min_level': 0.1,                               \
    #         'battery_capacity': 100,                                \
    #         'battery_charge_max': 50,                               \
    #         'battery_discharge_max': 50,                            \
    #         'battery_efficiency_charge': 0.9,                       \
    #         'battery_efficiency_discharge': 0.9,                    \
    #         'bel_ini_level': 0.5,                                   \
    #         'bel_fin_level': 0.0,                                   \
    #         'energy_price_buy': [2, 2, 3, 3, 4, 4],                 \
    #         'energy_price_sell':[2, 2, 3, 3, 4, 4],                 \
    #         'grid_fee_energy': 10,                                  \
    #         'grid_fee_power': 100,                                  \
    #         'grid_overcharge_penalty': 200,                         \
    #         'grid_power_contract': 20,                              \
    #         'dt': 1,                                                \
    # }

    # list of float numbers [kW]
    # list of float numbers [kW]
    # percentage of capacity
    # float number [kWh]
    # float number [kW]
    # float number [kW]
    # percentage
    # percentage
    # percentage of capacity
    # percentage of capacity
    # list of float numbers [EUR/kWh] or single float if constant
    # list of float numbers [EUR/kWh] or single float if constant
    # float number [EUR/kWh]
    # float number [EUR/kW]
    # float number [EUR/kW]
    # float number [kW]
    # float number



    periods = np.arange(1, len(data['generation'])+1)

    #generation = data['generation']
    generation = dict(zip(periods,  data['generation']))

    # if "demand" in data:
    #     demand = data['demand']
    # else:
    #     demand = [0] * len(data['generation'])
    if "demand" in data:
        demand = dict(zip(periods,  data['demand']))
    else:
        demand = [0] * len(data['generation'])
        demand = dict(zip(periods,  demand))

    if "battery_capacity" in data:
        battery_capacity = data['battery_capacity']
    else:
        battery_capacity = 0

    if "battery_min_level" in data:
        battery_min_level = data['battery_min_level']
    else:
        battery_min_level = 0

    if "battery_charge_max" in data:
        battery_charge_max = data['battery_charge_max']
    else:
        battery_charge_max = 0

    if "battery_discharge_max" in data:
        battery_discharge_max = data['battery_discharge_max']
    else:
        battery_discharge_max = 0

    if "battery_efficiency_charge" in data:
        battery_efficiency_charge = data['battery_efficiency_charge']
    else:
        battery_efficiency_charge = 0

    if "battery_efficiency_discharge" in data:
        battery_efficiency_discharge = data['battery_efficiency_discharge']
    else:
        battery_efficiency_discharge = 0

    if "bel_ini_level" in data:
        bel_ini_level = data['bel_ini_level']
    else:
        bel_ini_level = 0

    if "bel_fin_level" in data:
        bel_fin_level = data['bel_fin_level']
    else:
        bel_fin_level = 0



    #energy_price_buy = data['energy_price_buy']
    energy_price_buy = dict(zip(periods,  data['energy_price_buy']))
    #energy_price_sell = data['energy_price_sell']
    energy_price_sell = dict(zip(periods,  data['energy_price_sell']))
    grid_fee_energy = data['grid_fee_energy']
    grid_fee_power = data['grid_fee_power']


    if "grid_power_contract" in data:
        grid_overcharge_penalty = data['grid_overcharge_penalty']
    else:
        grid_overcharge_penalty = 0


    if "grid_power_contract" in data:
        grid_power_contract = data['grid_power_contract']
    else:
        grid_power_contract = 0

    if "dt" in data:
        dt = data['dt']
    else:
        dt = 1



    # Create model data input dictionary
    model_data = {None: {
        'T': periods,

        'generation': generation,
        'demand': demand,

        'battery_min_level': battery_min_level,
        'battery_capacity': battery_capacity,
        'battery_charge_max': battery_charge_max,
        'battery_discharge_max': battery_discharge_max,
        'battery_efficiency_charge': battery_efficiency_charge,
        'battery_efficiency_discharge': battery_efficiency_discharge,
        'bel_ini_level': bel_ini_level,
        'bel_fin_level': bel_fin_level,

        'energy_price_buy': energy_price_buy,
        'energy_price_sell': energy_price_sell,
        'grid_fee_energy': grid_fee_energy,
        'grid_fee_power': grid_fee_power,
        'grid_overcharge_penalty': grid_overcharge_penalty,
        'grid_power_contract': grid_power_contract,

        'dt': dt,
    }}

    return model_data


def microgrid_results(solution):
    
    s = dict()
    s['cost_energy'] = value(solution.COST_ENERGY[:])
    s['cost_grid_energy'] = value(solution.COST_GRID_ENERGY[:])
    s['cost_grid_power'] = value(solution.COST_GRID_POWER)
    
    s['power_overcharge'] = value(solution.P_OVER)
    s['power_buy'] = value(solution.P_BUY[:])
    s['power_sell'] = value(solution.P_SELL[:])
    s['battery_soc'] = value(solution.BEL[:])
    s['battery_charge'] = value(solution.B_IN[:])
    s['battery_discharge'] = value(solution.B_OUT[:])
    
    # Till pyomo version 5.7.3 there is an  inconsistency on how a VAR is called 
    # and how a VAR with fixed value
    if type(solution.P_CONTR.value) ==  SimpleParam:
        s['power_contract'] = value(solution.P_CONTR)()
    else:
        s['power_contract'] = value(solution.P_CONTR)
    
    return s



def microgrid_results_analysis(s):
    
    r = dict()
    
    r['energy_cost'] = sum(s['cost_energy'])
    r['grid_fee'] = sum(s['cost_grid_energy']) + s['cost_grid_power']
    r['total_cost'] = r['energy_cost'] + r['grid_fee']
    
    r['grid_energy_bought'] = sum(s['power_buy'])
    r['grid_energy_sold'] = sum(s['power_sell'])
    
    return r
    
    