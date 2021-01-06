import os
import json
import pprint

from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import RandomForestRegressor
import optuna
import lightgbm as lgb

from preprocess import Data, EngineerFeatures

# Optimizer class
class Optimize:
    # variable to get the data from the `Data` class
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
        regressor_name = trial.suggest_categorical("classifier", ["lgbr", "rf"])

        # define the respective hyperparameters for each regressor and
        # train the regressor
        if regressor_name == "lgbr":
            d_train = lgb.Dataset(X_train, label=y_train)
            params = {
                "application": "regression",
                "metric": "mean_squared_error",
                "verbosity": -1,
                "lambda_l1": trial.suggest_float(
                    "lambda_l1", 1e-8, 10.0, log=True
                ),
                "lambda_l2": trial.suggest_float(
                    "lambda_l2", 1e-8, 10.0, log=True
                ),
                "num_leaves": trial.suggest_int("num_leaves", 100, 500),
                "max_depth": trial.suggest_int("max_depth", 4, 30),
                "learning_rate": trial.suggest_float(
                    "learning_rate", 0.01, 1.0, log=True
                ),
                "feature_fraction": trial.suggest_float(
                    "feature_fraction", 0.3, 1.0
                ),
                "bagging_fraction": trial.suggest_float(
                    "bagging_fraction", 0.4, 1.0
                ),
                "bagging_freq": trial.suggest_int("bagging_freq", 1, 7),
                "min_child_samples": trial.suggest_int(
                    "min_child_samples", 5, 100
                ),
            }
            regressor_obj = lgb.train(params, d_train, num_boost_round=150)
        else:
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 100, 500),
                "max_depth": trial.suggest_int("max_depth", 4, 30),
                "max_features": trial.suggest_categorical(
                    "max_features", ["log2", "sqrt", None]
                ),
                "min_samples_split": trial.suggest_int(
                    "min_samples_split", 2, 10
                ),
            }
            regressor_obj = RandomForestRegressor(**params, n_jobs=-1)
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
        with open(os.path.join(path, "best_hyperparams.json"), "w") as f:
            f.write(hyperparams_dict)

    @staticmethod
    def print_param_stats(
        best_params: dict, study: optuna.create_study
    ) -> None:
        """
        Display the results
        """
        print("Best parameters: ")
        pprint.pprint(best_params, indent=4)
        od = optuna.importance.get_param_importances(study)
        print("Parameter importance for the best model: ")
        for k, v in od.items():
            pprint.pprint((k, v), indent=4)


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
    study.optimize(opt.optimize, n_trials=10)
    best_params_ = study.best_params

    # store and display the results
    opt.write_to_json(model_path, best_params=best_params_)
    opt.print_param_stats(best_params_, study=study)
