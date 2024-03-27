import cvxpy as cp
import numpy as np
import pyomo.environ as pyo
from measure_optimize import (
    MeasurementOptimizer,
    SensitivityData,
    MeasurementData,
    CovarianceStructure,
    ObjectiveLib,
)
import pickle
import time

# optimization options
objective = ObjectiveLib.A

test = True


# choose to run a set of test budgets, or all budgets 
if test:
    budget_set = [3000, 5000]
else:
    budget_set = np.linspace(1000, 5000, 11)


# mixed integer or not 
mixed_integer_opt = True

#file_store_name = "./cvxpy_results/cvxpy_A_"
file_store_name = None


def cvxpy_problem(objective, budget_opt, mixed_integer_opt, file_store_name):
    """
    Run the Cvxpy problem for a set of budget 
    """
    # set up problem formulation

    # number of time points for DCM
    Nt = 8

    # maximum manual measurement number for each measurement
    max_manual_num = 10
    # minimal measurement interval
    min_interval_num = 10.0
    # maximum manual measurement number for all measurements
    total_max_manual_num = 10

    # index of columns of SCM and DCM in Q
    static_ind = [0, 1, 2]
    dynamic_ind = [3, 4, 5]
    # this index is the number of SCM + nubmer of DCM, not number of DCM timepoints
    all_ind = static_ind + dynamic_ind
    num_total_measure = len(all_ind)

    # meausrement names
    all_names_strategy3 = [
        "CA.static",
        "CB.static",
        "CC.static",
        "CA.dynamic",
        "CB.dynamic",
        "CC.dynamic",
    ]

    # define static costs
    static_cost = [2000, 2000, 2000, 200, 200, 200]  # CA  # CB  # CC  # CA  # CB  # CC

    # each static-cost measure has no per-sample cost
    dynamic_cost = [0] * len(static_ind)
    # each dynamic-cost measure costs $ 400 per sample
    dynamic_cost.extend([400] * len(dynamic_ind))

    # error covariance matrix
    error_cov = [
        [1, 0.1, 0.1, 1, 0.1, 0.1],
        [0.1, 4, 0.5, 0.1, 4, 0.5],
        [0.1, 0.5, 8, 0.1, 0.5, 8],
        [1, 0.1, 0.1, 1, 0.1, 0.1],
        [0.1, 4, 0.5, 0.1, 4, 0.5],
        [0.1, 0.5, 8, 0.1, 0.5, 8],
    ]

    ## change the correlation of DCM VS SCM to half the original value
    # variance
    var_list = [1, 4, 8, 1, 4, 8]
    # standard deviation
    std_list = [np.sqrt(var_list[i]) for i in range(len(var_list))]

    # Generate correlation matrix
    corr_original = [[0] * len(var_list) for i in range(len(var_list))]

    # compute correlation, corr[i,j] = cov[i,j]/std[i]/std[j]
    for i in range(len(var_list)):
        # loop over Nm
        for j in range(len(var_list)):
            corr_original[i][j] = error_cov[i][j] / std_list[i] / std_list[j]

    # DCM-SCM correlations are half of DCM-DCM or SCM-SCM correlation
    corr_num = 0.5

    # loop over SCM rows
    for i in range(len(static_ind)):
        # loop over DCM columns
        for j in range(len(static_ind), len(var_list)):
            # correlation matrix is symmetric
            # we make DCM-SCM correlation half of its original value
            corr_original[i][j] *= corr_num
            corr_original[j][i] *= corr_num

    # update covariance matrix
    # change back from correlation matrix
    for i in range(len(var_list)):
        for j in range(len(var_list)):
            error_cov[i][j] = corr_original[i][j] * std_list[i] * std_list[j]

    ## define MeasurementData object
    measure_info = MeasurementData(
        all_names_strategy3,  # name string
        all_ind,  # jac_index: measurement index in Q
        static_cost,  # static costs
        dynamic_cost,  # dynamic costs
        min_interval_num,  # minimal time interval between two timepoints
        max_manual_num,  # maximum number of timepoints for each measurement
        total_max_manual_num,  # maximum number of timepoints for all measurement
    )



    # create data object to pre-compute Qs
    # read jacobian from the source csv
    # Nt is the number of time points for each measurement
    jac_info = SensitivityData("./kinetics_source_data/Q_drop0.csv", Nt)
    static_measurement_index = [
        0,
        1,
        2,
    ]  # the index of CA, CB, CC in the jacobian array, considered as SCM
    dynamic_measurement_index = [
        0,
        1,
        2,
    ]  # the index of CA, CB, CC in the jacobian array, also considered as DCM
    jac_info.get_jac_list(
        static_measurement_index,  # the index of SCMs in the jacobian array
        dynamic_measurement_index,
    )  # the index of DCMs in the jacobian array

    # use MeasurementOptimizer to pre-compute the unit FIMs
    calculator = MeasurementOptimizer(
        jac_info,  # SensitivityData object
        measure_info,  # MeasurementData object
        error_cov=error_cov,  # error covariance matrix
        error_opt=CovarianceStructure.measure_correlation,  # error covariance options
        print_level = 3
    )

    # calculate a list of unit FIMs
    calculator.assemble_unit_fims()

    # number of dynamic times 
    num_dynamic_time = np.linspace(0, 60, 9)

    static_dynamic = [[0, 3], [1, 4], [2, 5]]  # These pairs cannot be chosen simultaneously
    time_interval_for_all = True

    # map the timepoint index to its real time
    dynamic_time_dict = {}
    for i, tim in enumerate(num_dynamic_time[1:]):
        dynamic_time_dict[i] = np.round(tim, decimals=2)


    # go over budget
    for b in budget_opt:
        # continuous optimization with Cvxpy 
        calculator.continuous_optimization_cvxpy(objective=objective, # objective function
                                                 mixed_integer = mixed_integer_opt, # mixed integer or not
                                                 budget=b, # budget
                                                 static_dynamic_pair = static_dynamic, # default option for SCM-DCM pairs 
                                                 time_interval_all_dynamic = time_interval_for_all, # time intervals
                                                 num_dynamic_t_name=num_dynamic_time,  # number of time points of DCMs
                                                 solver="MOSEK",
                                                 store_name = file_store_name)

        
        

cvxpy_problem(objective, budget_set, mixed_integer_opt, file_store_name)

    