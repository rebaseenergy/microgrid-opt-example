import pandas as pd
import numpy as np
import numpy_financial as npf
from datetime import datetime


def financial_kpis(invest_cost, savings, discount_rate, project_lifespan):
    
    # This function returns: 
    # Cash flow table    
    # Net present value (NPV) [$]
    # Payback time [year]
    # Internal rate of return (IRR) [%]
    # Total / annual return of investment (ROI) [%]
    
    # Example
    # discount_rate = 0.08
    # invest_cost = 2443750
    # savings = 262800
    # project_lifespan = 30
    # cf, npv, payback_time, irr, roi_total, roi_annual = kpis(invest_cost, savings, discount_rate, project_lifespan)
    
    # Create cash flow table
    cf = cash_flow_table(invest_cost, savings, discount_rate, project_lifespan)

    # Net present value (NPV)
    npv = cf['Net Present Value'].iloc[-1]
    
    # Payback time
    nvp_sign = cf['Net Present Value'].gt(0)
    
    if nvp_sign.iloc[0] == True:
        payback_time = 'Less than a year'
        
    elif nvp_sign.iloc[-1] == False:
        payback_time = 'More than ' + str(project_lifespan) + ' years (project life span)'
        
    else:
        r = cf['Net Present Value'].gt(0).idxmax() # row that NPV is becoming positive
        
        payback_time = r-cf['Net Present Value'].iloc[r-1]/(cf['Net Present Value'].iloc[r] - cf['Net Present Value'].iloc[r-1])
    
    
    # Internal rate of return (IRR)
    cashflows = [-invest_cost] + cf['Annual Savings'].values.tolist()
    irr = round(npf.irr(cashflows),3)*100

    
    # Return of investment (ROI)
    if invest_cost != 0:
        roi_total = (sum(cf['Annual Savings']) - invest_cost)/invest_cost
        roi_annual = (1+roi_total)**(1/project_lifespan)-1
        roi_total = roi_total*100
        roi_annual = roi_annual*100
    else:
        roi_total = np.nan
        roi_annual = np.nan
        
    return cf, npv, payback_time, irr, roi_total, roi_annual


def cash_flow_table(invest_cost, savings, discount_rate, project_lifespan):

    data = []
    cashflow_accumulated = 0
    year = datetime.now().year
    for i in range(1,project_lifespan+1):
        
        year = year + 1
        
        cashflow = savings
        
        cashflow_discounted = savings/((1+discount_rate)**i)
        
        cashflow_accumulated = cashflow_accumulated + cashflow_discounted
        
        net_present_value = cashflow_accumulated - invest_cost
        
        data.append([year, cashflow, cashflow_discounted, cashflow_accumulated, net_present_value])
        
    
    cf = pd.DataFrame(data, columns=['Year', 'Annual Savings', 'Annual Savings Discounted', 'Accumulated Discounted Savings', 'Net Present Value'])

    return cf