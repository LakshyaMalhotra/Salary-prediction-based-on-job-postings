__author__ = "Lakshya Malhotra"
__copyright__ = "Copyright (c) 2021 Lakshya Malhotra"

# library imports
import os
import json

from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
import optuna
import lightgbm as lgb

from preprocess import Data, EngineerFeatures

# Optimizer class
class Optimize:
    # class variable to get the data from the `Data` class
    train_df = None

    @staticmethod
    def optimize(trial) -> float:
        """
        Optimize the hyperparameters of the regression model and return the 
        loss for the given trial
        """
        features = [
            col
            for col in Optimize.train_df.columns
            if col not in ["jobId", "salary"]
        ]
        # get the features and target from the original dataframe
        X = Optimize.train_df.loc[:, features]
        y = Optimize.train_df.salary

        # split features and target into training and validation set
        X_train, X_valid, y_train, y_valid = train_test_split(
            X, y, test_size=0.2, random_state=23
        )

        # randomly select the regressor to use for optimization
        regressor_name = trial.suggest_categorical("regressor", ["lgbr", "rf"])

        # define the respective hyperparameters for each regressor and
        # train the regressor
        if regressor_name == "lgbr":
            params = {
                "metric": "mean_squared_error",
                "verbosity": -1,
                "n_jobs": -1,
                "n_estimators": trial.suggest_int("n_estimators", 100, 200),
                "reg_alpha": trial.suggest_float(
                    "reg_alpha", 1e-8, 10.0, log=True
                ),
                "reg_lambda": trial.suggest_float(
                    "reg_lambda", 1e-8, 10.0, log=True
                ),
                "num_leaves": trial.suggest_int("num_leaves", 100, 500),
                "max_depth": trial.suggest_int("max_depth", 4, 30),
                "learning_rate": trial.suggest_float(
                    "learning_rate", 0.01, 1.0, log=True
                ),
                "colsample_bytree": trial.suggest_float(
                    "colsample_bytree", 0.3, 1.0
                ),
                "subsample": trial.suggest_float("subsample", 0.4, 1.0),
                "subsample_freq": trial.suggest_int("subsample_freq", 1, 7),
                "min_child_samples": trial.suggest_int(
                    "min_child_samples", 5, 100
                ),
            }
            regressor_obj = lgb.LGBMRegressor(**params)
        else:
            params = {
                "n_jobs": -1,
                "n_estimators": trial.suggest_int("n_estimators", 100, 500),
                "max_depth": trial.suggest_int("max_depth", 4, 30),
                "max_features": trial.suggest_categorical(
                    "max_features", ["log2", "sqrt", None]
                ),
                "min_samples_split": trial.suggest_int(
                    "min_samples_split", 2, 10
                ),
            }
            regressor_obj = RandomForestRegressor(**params)

        # fit the regressor on training data
        regressor_obj.fit(X_train, y_train)

        # make predictions on the validation data
        y_pred = regressor_obj.predict(X_valid)

        # get the loss from the predictions
        error = mean_squared_error(y_valid, y_pred)

        return error

    @staticmethod
    def write_to_json(path: str, best_params: dict) -> None:
        """
        Write the best hyperparameters to a JSON file
        """
        hyperparams_dict = json.dumps(best_params)
        path_to_json = os.path.join(path, "best_hyperparams.json")
        with open(path_to_json, "w") as f:
            f.write(hyperparams_dict)

        return path_to_json

    @staticmethod
    def print_param_stats(
        best_params: dict, study: optuna.create_study
    ) -> None:
        """
        Display the results
        """
        print("Best parameters: ")
        print(best_params)
        od = optuna.importance.get_param_importances(study)
        print("Parameter importance for the best model: ")
        for k, v in od.items():
            print(k, v)


if __name__ == "__main__":
    # define variables
    path = "data/"
    model_path = "models/"
    train_feature_file = os.path.join(path, "train_features.csv")
    train_target_file = os.path.join(path, "train_salaries.csv")
    test_file = os.path.join(path, "test_features.csv")

    cat_vars = ["companyId", "jobType", "degree", "major", "industry"]
    num_vars = ["yearsExperience", "milesFromMetropolis"]
    target_var = "salary"
    unique_var = "jobId"

    print("Loading and preprocessing data...")
    # instantiate the `Data` class and load the data
    data = Data(
        train_feature_file,
        train_target_file,
        test_file,
        cat_vars=cat_vars,
        num_vars=num_vars,
        target_var=target_var,
        unique_var=unique_var,
    )
    print("Performing feature engineering and creating K-fold CV...")
    # perform feature engineering and update the data
    fe = EngineerFeatures(data)
    fe.add_features()

    print("Optimizing the model hyperparameters...")
    # assign data to the class variable and instantiate the optimizer object
    Optimize.train_df = data.train_df
    opt = Optimize()

    # create a study object and start tuning the hyperprameters
    study = optuna.create_study(direction="minimize")
    study.optimize(opt.optimize, n_trials=30)
    best_params_ = study.best_params

    # store and display the results
    json_path = opt.write_to_json(model_path, best_params=best_params_)
    print(f"Best params are saved to file: {json_path}")
    opt.print_param_stats(best_params_, study=study)
