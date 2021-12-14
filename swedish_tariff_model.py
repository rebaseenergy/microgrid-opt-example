from pyomo.environ import ConcreteModel, AbstractModel
from pyomo.environ import Set,Param,Var,Objective,Constraint
from pyomo.environ import PositiveIntegers, NonNegativeReals, Reals
from pyomo.environ import SolverFactory, minimize
from pyomo.environ import value
from pyomo.core.base.param import SimpleParam
import numpy as np


def solve_model(model_instance, solver):
    if 'path' in solver:
        optimizer = SolverFactory(solver['name'], executable=solver['path'])
    else:
        optimizer = SolverFactory(solver['name'])

    optimizer.solve(model_instance, tee=True, keepfiles=False)


    return model_instance


def netmetering_model(model_data):


    model = ConcreteModel()

    ## SETS
    model.T = Set(dimen=1, ordered=True, initialize=model_data[None]['T']) # Periods
    model.M = Set(dimen=1, ordered=True, initialize=np.array(list(set(model_data[None]['month_order'].values())))) # Months



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
    model.battery_grid_charging         = Param(initialize=model_data[None]['battery_grid_charging'])
    
    model.energy_price_buy              = Param(model.T, initialize=model_data[None]['energy_price_buy'])
    model.energy_price_sell             = Param(model.T, initialize=model_data[None]['energy_price_sell'])
    
    model.grid_fixed_fee                = Param(initialize=model_data[None]['grid_fixed_fee'])
    model.grid_energy_import_fee        = Param(model.T, within=Reals, initialize=model_data[None]['grid_energy_import_fee'])
    model.grid_energy_export_fee        = Param(model.T, within=Reals, initialize=model_data[None]['grid_energy_export_fee'])
    
    model.grid_power_import_fee         = Param(model.T, within=Reals, initialize=model_data[None]['grid_power_import_fee'])
    model.grid_power_export_fee         = Param(model.T, within=Reals, initialize=model_data[None]['grid_power_export_fee'])
    
    model.import_penalty                = Param(initialize=model_data[None]['import_penalty'])
    
    model.dt                            = Param(initialize=model_data[None]['dt'])
    


    ## VARIABLE LIMITS
    def soc_limits(model, t):
        return (model.battery_min_level*model.battery_capacity, model.battery_capacity)
    def charge_limits(model, t):
        return (0.0, model.battery_charge_max)
    def discharge_limits(model, t):
        return (0.0, model.battery_discharge_max)


    ## VARIABLES
    model.COST_ENERGY                   = Var(model.T, within=Reals)
    model.COST_GRID_ENERGY_IMPORT       = Var(model.T, within=Reals)
    model.COST_GRID_ENERGY_EXPORT       = Var(model.T, within=Reals)
    model.COST_GRID_POWER_IMPORT        = Var(model.T, within=NonNegativeReals)
    model.COST_GRID_POWER_EXPORT        = Var(model.T, within=NonNegativeReals)
    model.COST_GRID_POWER               = Var(model.T, within=Reals)
    model.COST_GRID_POWER_MAX           = Var(model.M, within=Reals)
    model.COST_GRID_FIXED               = Var(within=Reals)
    

    model.P_BUY                     = Var(model.T, within=NonNegativeReals)
    model.P_SELL                    = Var(model.T, within=NonNegativeReals)
    model.BEL                       = Var(model.T, within=NonNegativeReals, bounds=soc_limits)
    model.B_IN                      = Var(model.T, within=NonNegativeReals, bounds=charge_limits)
    model.B_OUT                     = Var(model.T, within=NonNegativeReals, bounds=discharge_limits)




    ## OBJECTIVE
    # Minimize cost
    def total_cost(model):
        return sum(model.COST_ENERGY[t] + model.COST_GRID_ENERGY_IMPORT[t] + model.COST_GRID_ENERGY_EXPORT[t] for t in model.T) \
        + sum(model.COST_GRID_POWER_MAX[m] for m in model.M) + model.COST_GRID_FIXED \
        + model.import_penalty*sum(model.P_BUY[t]*model.dt for t in model.T)
    model.total_cost = Objective(rule=total_cost, sense=minimize)




    ## CONSTRAINTS
    # Energy cost
    def energy_cost(model, t):
        return model.COST_ENERGY[t] == model.energy_price_buy[t]*model.P_BUY[t]*model.dt - model.energy_price_sell[t]*model.P_SELL[t]*model.dt
    model.energy_cost = Constraint(model.T, rule=energy_cost)



    # Grid fixed cost
    def grid_fixed_cost(model):
        return model.COST_GRID_FIXED == model.grid_fixed_fee*len(model.M)
    model.grid_fixed_cost = Constraint(rule=grid_fixed_cost)
    


    # Grid energy import cost
    def grid_energy_import_cost(model, t):
        return model.COST_GRID_ENERGY_IMPORT[t] == model.grid_energy_import_fee[t]*model.P_BUY[t]*model.dt
    model.grid_energy_import_cost = Constraint(model.T, rule=grid_energy_import_cost)
    
    # Grid energy export cost
    def grid_energy_export_cost(model, t):
        return model.COST_GRID_ENERGY_EXPORT[t] == model.grid_energy_export_fee[t]*model.P_SELL[t]*model.dt
    model.grid_energy_export_cost = Constraint(model.T, rule=grid_energy_export_cost)



    # Grid power import cost
    def grid_power_import_cost(model, t):
        return model.COST_GRID_POWER_IMPORT[t] >= model.grid_power_import_fee[t]*(model.P_BUY[t]-model.P_SELL[t])
    model.grid_power_import_cost = Constraint(model.T, rule=grid_power_import_cost)
    
    # Grid power export cost
    def grid_power_export_cost(model, t):
        return model.COST_GRID_POWER_EXPORT[t] >= model.grid_power_export_fee[t]*(model.P_SELL[t]-model.P_BUY[t])
    model.grid_power_export_cost = Constraint(model.T, rule=grid_power_export_cost)


    # Grid power cost
    def grid_power_cost(model, t):
        return model.COST_GRID_POWER[t] == model.COST_GRID_POWER_IMPORT[t] + model.COST_GRID_POWER_EXPORT[t]
    model.grid_power_cost = Constraint(model.T, rule=grid_power_cost)


    # Max grid cost
    def max_grid_power_cost(model, t):
        return model.COST_GRID_POWER_MAX[model_data[None]['month_order'][t]] >= model.COST_GRID_POWER[t]
    model.max_grid_power_cost = Constraint(model.T, rule=max_grid_power_cost)


    # Energy balance
    def energy_balance(model, t):
        return model.P_SELL[t] - model.P_BUY[t] ==  model.generation[t] + model.B_OUT[t] - model.B_IN[t] - model.demand[t]
    model.energy_balance = Constraint(model.T, rule=energy_balance)


    # Battery charging from grid
    def no_grid_charging(model, t):
        if value(model.battery_grid_charging) == False:
            return model.P_BUY[t] <= model.demand[t]   
        else:
            return Constraint.Skip
    model.no_grid_charging = Constraint(model.T, rule=no_grid_charging)


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
    

    return model


def netmetering_model_input(data):


    periods = np.arange(1, len(data['generation'])+1)
    generation = dict(zip(periods,  data['generation']))


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
        
    if "battery_grid_charging" in data:
        battery_grid_charging = data['battery_grid_charging']
    else:
        battery_grid_charging = True        
        
    if "import_penalty" in data:
        import_penalty = data['import_penalty']
    else:
        import_penalty = 0 



    energy_price_buy = dict(zip(periods,  data['energy_price_buy']))
    energy_price_sell = dict(zip(periods,  data['energy_price_sell']))
    
    grid_fixed_fee = data['grid_fixed_fee']
    grid_energy_import_fee = dict(zip(periods,  data['grid_energy_import_fee']))
    grid_energy_export_fee = dict(zip(periods,  data['grid_energy_export_fee']))
    grid_power_import_fee = dict(zip(periods,  data['grid_power_import_fee']))
    grid_power_export_fee = dict(zip(periods,  data['grid_power_export_fee']))


    if "dt" in data:
        dt = data['dt']
    else:
        dt = 1

    month_order = dict(zip(periods,  data['month_order']))

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
        'battery_grid_charging': battery_grid_charging,
        'bel_ini_level': bel_ini_level,
        'bel_fin_level': bel_fin_level,

        'energy_price_buy': energy_price_buy,
        'energy_price_sell': energy_price_sell,
        
        'grid_fixed_fee': grid_fixed_fee,
        'grid_energy_import_fee': grid_energy_import_fee,
        'grid_energy_export_fee': grid_energy_export_fee,
        'grid_power_import_fee': grid_power_import_fee,
        'grid_power_export_fee': grid_power_export_fee,
        'import_penalty': import_penalty,

        'month_order': month_order,
        'dt': dt,
    }}

    return model_data


def netmetering_model_results(solution):
    
    s = dict()
    
    
    s['cost_total'] = value(sum(solution.COST_ENERGY[t] + solution.COST_GRID_ENERGY_IMPORT[t] - solution.COST_GRID_ENERGY_EXPORT[t] for t in solution.T) \
        + sum(solution.COST_GRID_POWER_MAX[m] for m in solution.M) + solution.COST_GRID_FIXED)

    s['cost_energy'] = value(solution.COST_ENERGY[:])
    s['cost_grid_energy_import'] = value(solution.COST_GRID_ENERGY_IMPORT[:])
    s['cost_grid_energy_export'] = value(solution.COST_GRID_ENERGY_EXPORT[:])
    s['cost_grid_power'] = value(solution.COST_GRID_POWER[:])
    s['cost_grid_power_max'] = value(solution.COST_GRID_POWER_MAX[:])
    s['cost_grid_power_fixed'] = value(solution.COST_GRID_FIXED)
    

    s['power_buy'] = value(solution.P_BUY[:])
    s['power_sell'] = value(solution.P_SELL[:])
    
    s['battery_soc'] = value(solution.BEL[:])
    s['battery_charge'] = value(solution.B_IN[:])
    s['battery_discharge'] = value(solution.B_OUT[:])

    
    return s


    
    