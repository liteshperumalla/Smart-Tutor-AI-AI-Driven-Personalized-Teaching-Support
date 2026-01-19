#!/usr/bin/env python3
"""
Script to add remaining 50 queries to test_dataset.json
"""

import json

# Read existing dataset
with open('test_dataset.json', 'r') as f:
    dataset = json.load(f)

# Remaining 50 queries (q051-q100)
remaining_queries = [
    {
        "id": "q051",
        "query": "What is image classification?",
        "intent": "definitional",
        "complexity": "low",
        "ground_truth_answer": "Image classification assigns a label to an entire image from a predefined set of categories. Input: image, Output: class label. Architectures: CNNs (VGG, ResNet, EfficientNet). Process: feature extraction through convolutional layers, global pooling, fully connected layers for classification. Datasets: ImageNet, CIFAR-10. Metrics: accuracy, top-5 accuracy. Applications: medical diagnosis, content moderation, product categorization. Differs from object detection (doesn't locate objects) and segmentation (doesn't provide pixel-level labels).",
        "relevant_doc_ids": ["doc_image_classification_778", "doc_cv_basics_689"],
        "expected_sources": ["computer_vision_fundamentals.pdf", "image_classification.pdf"],
        "keywords": ["image classification", "CNN", "ResNet", "computer vision", "ImageNet"]
    },
    {
        "id": "q052",
        "query": "How do I handle missing data in datasets?",
        "intent": "procedural",
        "complexity": "low",
        "ground_truth_answer": "Missing data handling strategies: 1) Deletion: remove rows/columns with missing values (if <5% missing), 2) Imputation: fill with mean/median/mode (numerical), most frequent category (categorical), 3) Advanced imputation: KNN imputation, regression imputation, iterative imputer (MICE), 4) Indicator variable: add binary column showing missingness, 5) Use algorithms that handle missing values (XGBoost, LightGBM). Choice depends on: missing percentage, missing mechanism (MCAR, MAR, MNAR), data type. Always analyze why data is missing before choosing strategy.",
        "relevant_doc_ids": ["doc_missing_data_801", "doc_data_preprocessing_712"],
        "expected_sources": ["missing_data_handling.pdf", "data_cleaning.pdf"],
        "keywords": ["missing data", "imputation", "mean imputation", "data preprocessing", "NA values"]
    },
    {
        "id": "q053",
        "query": "What is gradient clipping?",
        "intent": "definitional",
        "complexity": "medium",
        "ground_truth_answer": "Gradient clipping prevents exploding gradients by limiting the magnitude of gradients during backpropagation. Two methods: 1) Clip by value: if gradient > threshold, set to threshold, 2) Clip by norm: if L2 norm of gradients > threshold, scale down proportionally. Commonly used in RNNs where exploding gradients are frequent. Typical threshold: 1.0 to 10.0. Benefits: training stability, prevents NaN/Inf values, allows higher learning rates. Differs from gradient normalization. Most frameworks provide built-in gradient clipping.",
        "relevant_doc_ids": ["doc_gradient_clipping_823", "doc_training_stability_734"],
        "expected_sources": ["gradient_clipping.pdf", "rnn_training.pdf"],
        "keywords": ["gradient clipping", "exploding gradients", "training stability", "backpropagation"]
    },
    {
        "id": "q054",
        "query": "What is the difference between classification and regression?",
        "intent": "comparison",
        "complexity": "low",
        "ground_truth_answer": "Classification predicts discrete categories/classes (spam/not spam, cat/dog/bird). Output is categorical. Metrics: accuracy, precision, recall, F1. Algorithms: logistic regression, SVM, decision trees, neural networks. Regression predicts continuous numerical values (house price, temperature, stock price). Output is numerical. Metrics: MSE, RMSE, MAE, R². Algorithms: linear regression, polynomial regression, neural networks. Key difference: output type (discrete vs continuous). Some algorithms work for both with different loss functions.",
        "relevant_doc_ids": ["doc_ml_tasks_845", "doc_supervised_learning_756"],
        "expected_sources": ["machine_learning_tasks.pdf", "prediction_types.pdf"],
        "keywords": ["classification", "regression", "supervised learning", "prediction", "discrete", "continuous"]
    },
    {
        "id": "q055",
        "query": "What is model interpretability?",
        "intent": "definitional",
        "complexity": "medium",
        "ground_truth_answer": "Model interpretability is the ability to explain and understand how a model makes predictions. Important for trust, debugging, regulatory compliance, and fairness. Techniques: 1) Model-specific: decision tree visualization, linear model coefficients, 2) Model-agnostic: SHAP values, LIME, partial dependence plots, permutation importance, 3) Example-based: prototype selection, counterfactual explanations. Trade-off: complex models (deep learning, ensembles) are often more accurate but less interpretable than simple models (linear regression, decision trees). Growing field of Explainable AI (XAI).",
        "relevant_doc_ids": ["doc_interpretability_867", "doc_explainable_ai_778"],
        "expected_sources": ["model_interpretability.pdf", "explainable_ai.pdf"],
        "keywords": ["interpretability", "explainability", "SHAP", "LIME", "XAI", "transparency"]
    },
    {
        "id": "q056",
        "query": "What is SHAP?",
        "intent": "definitional",
        "complexity": "high",
        "ground_truth_answer": "SHAP (SHapley Additive exPlanations) is a unified approach to explain model predictions based on Shapley values from game theory. It calculates each feature's contribution to the prediction by considering all possible feature combinations. Properties: local accuracy, missingness, consistency. Outputs: feature importance (global), force plots (local), summary plots, dependence plots. Works with any model (model-agnostic). Computationally expensive for large datasets; approximations: TreeSHAP (tree models), KernelSHAP (any model), DeepSHAP (neural networks). Provides both positive and negative contributions per feature.",
        "relevant_doc_ids": ["doc_shap_889", "doc_shapley_values_801"],
        "expected_sources": ["shap_explanation.pdf", "feature_importance.pdf"],
        "keywords": ["SHAP", "Shapley values", "feature importance", "model explanation", "interpretability"]
    },
    {
        "id": "q057",
        "query": "How do I debug a model that's not learning?",
        "intent": "troubleshooting",
        "complexity": "medium",
        "ground_truth_answer": "Debugging steps: 1) Check data: verify labels, check for data leakage, visualize samples, 2) Simplify: start with small model, overfit single batch, 3) Check implementation: verify loss calculation, check gradient flow, validate data pipeline, 4) Adjust hyperparameters: increase learning rate, reduce regularization, try different optimizer, 5) Check architecture: ensure sufficient capacity, verify activation functions, check weight initialization, 6) Monitor training: plot loss curves, check gradient magnitudes, visualize weights/activations, 7) Baseline: compare to simple model. Common issues: too low learning rate, incorrect labels, vanishing gradients, dead ReLU.",
        "relevant_doc_ids": ["doc_debug_training_912", "doc_troubleshooting_823"],
        "expected_sources": ["debugging_neural_networks.pdf", "training_troubleshooting.pdf"],
        "keywords": ["debugging", "not learning", "training issues", "loss not decreasing", "troubleshooting"]
    },
    {
        "id": "q058",
        "query": "What is batch size and how does it affect training?",
        "intent": "conceptual",
        "complexity": "medium",
        "ground_truth_answer": "Batch size is the number of training samples processed before updating model weights. Effects: Large batches (256+): faster training (parallelization), more stable gradients, less noise, may converge to sharp minima (poor generalization), requires more memory. Small batches (16-32): slower training, noisy gradients (acts as regularization), better generalization, less memory. Mini-batch (32-128) is common trade-off. Batch size interacts with learning rate: larger batches may need higher learning rates. Techniques: gradient accumulation for large effective batch size with limited memory. Choice depends on hardware, dataset size, and task.",
        "relevant_doc_ids": ["doc_batch_size_934", "doc_training_hyperparameters_845"],
        "expected_sources": ["batch_size_effects.pdf", "hyperparameter_guide.pdf"],
        "keywords": ["batch size", "mini-batch", "training", "memory", "gradient", "convergence"]
    },
    {
        "id": "q059",
        "query": "What is early stopping?",
        "intent": "definitional",
        "complexity": "low",
        "ground_truth_answer": "Early stopping halts training when validation performance stops improving, preventing overfitting. Monitor validation metric (loss, accuracy), track best performance, stop if no improvement for N epochs (patience). Save best model checkpoint, not final. Benefits: prevents overfitting, reduces training time, automatic regularization. Typical patience: 5-20 epochs. Requires validation set. Can combine with learning rate reduction: reduce LR when plateauing before stopping. Modern practice: use with model checkpointing to restore best weights. Essential technique in deep learning training pipelines.",
        "relevant_doc_ids": ["doc_early_stopping_956", "doc_regularization_867"],
        "expected_sources": ["early_stopping.pdf", "training_strategies.pdf"],
        "keywords": ["early stopping", "validation", "overfitting", "patience", "model checkpoint"]
    },
    {
        "id": "q060",
        "query": "What is the difference between bagging and boosting?",
        "intent": "comparison",
        "complexity": "medium",
        "ground_truth_answer": "Bagging (Bootstrap Aggregating): trains multiple models in parallel on random subsets of data (with replacement), averages predictions. Reduces variance, works well with unstable models (decision trees). Example: Random Forest. Models are independent. Boosting: trains models sequentially, each correcting predecessors' errors. Focuses on hard examples by reweighting. Reduces both bias and variance. Examples: AdaBoost, XGBoost, Gradient Boosting. Models are dependent. Bagging is less prone to overfitting; boosting can overfit if not regularized. Boosting often achieves better performance but is more sensitive to noise and outliers.",
        "relevant_doc_ids": ["doc_ensemble_comparison_978", "doc_bagging_boosting_889"],
        "expected_sources": ["ensemble_methods.pdf", "bagging_vs_boosting.pdf"],
        "keywords": ["bagging", "boosting", "ensemble", "Random Forest", "XGBoost", "variance", "bias"]
    },
    {
        "id": "q061",
        "query": "What is a decision tree?",
        "intent": "definitional",
        "complexity": "low",
        "ground_truth_answer": "A decision tree is a tree-structured model that makes predictions by learning decision rules from features. Nodes represent feature tests, branches represent outcomes, leaves represent predictions. Splitting criteria: Gini impurity (classification), entropy (information gain), MSE (regression). Building process: recursively split data to maximize information gain until stopping criteria (max depth, min samples). Advantages: interpretable, handles non-linear relationships, no feature scaling needed, works with categorical/numerical data. Disadvantages: prone to overfitting, unstable (small data changes cause different trees), biased to dominant classes. Use pruning to reduce overfitting.",
        "relevant_doc_ids": ["doc_decision_trees_1001", "doc_tree_based_models_912"],
        "expected_sources": ["decision_trees.pdf", "tree_algorithms.pdf"],
        "keywords": ["decision tree", "Gini", "entropy", "classification", "splitting", "interpretable"]
    },
    {
        "id": "q062",
        "query": "What is Random Forest?",
        "intent": "definitional",
        "complexity": "medium",
        "ground_truth_answer": "Random Forest is an ensemble of decision trees trained on random subsets of data (bagging) with random feature selection at each split. Each tree votes; majority wins (classification) or average (regression). Hyperparameters: n_estimators (number of trees), max_features (features per split), max_depth. Advantages: reduces overfitting vs single tree, handles high-dimensional data, provides feature importance, robust to outliers, parallelizable. Disadvantages: less interpretable than single tree, larger memory footprint, slower prediction. Works well out-of-the-box with minimal tuning. One of the most effective classical ML algorithms.",
        "relevant_doc_ids": ["doc_random_forest_1023", "doc_ensemble_trees_934"],
        "expected_sources": ["random_forest.pdf", "ensemble_methods.pdf"],
        "keywords": ["Random Forest", "ensemble", "decision trees", "bagging", "feature importance"]
    },
    {
        "id": "q063",
        "query": "How does logistic regression work?",
        "intent": "conceptual",
        "complexity": "medium",
        "ground_truth_answer": "Logistic regression is a classification algorithm that models probability of binary outcome using sigmoid function. Linear combination of features: z = w·x + b, then σ(z) = 1/(1+e^(-z)) maps to [0,1]. Threshold at 0.5 for classification. Training minimizes log loss (cross-entropy) using gradient descent. Despite 'regression' in name, it's for classification. For multi-class: one-vs-rest or multinomial (softmax) logistic regression. Advantages: simple, interpretable (coefficients show feature influence), probabilistic outputs, works well with linearly separable data. Disadvantages: assumes linear decision boundary, sensitive to outliers, requires feature scaling.",
        "relevant_doc_ids": ["doc_logistic_regression_1045", "doc_classification_algorithms_956"],
        "expected_sources": ["logistic_regression.pdf", "linear_models.pdf"],
        "keywords": ["logistic regression", "sigmoid", "classification", "probability", "log loss"]
    },
    {
        "id": "q064",
        "query": "What is feature scaling and why is it important?",
        "intent": "conceptual",
        "complexity": "low",
        "ground_truth_answer": "Feature scaling transforms features to similar ranges, improving algorithm performance. Methods: 1) Normalization (Min-Max): scales to [0,1] range, 2) Standardization (Z-score): zero mean, unit variance, 3) Robust scaling: uses median/IQR (robust to outliers). Importance: gradient descent converges faster with scaled features, distance-based algorithms (KNN, SVM, K-means) require similar scales, prevents large-magnitude features from dominating, regularization works better. Not needed for: tree-based models (Random Forest, XGBoost). Apply same scaling to train and test data using fitted scalers from training.",
        "relevant_doc_ids": ["doc_feature_scaling_1067", "doc_preprocessing_978"],
        "expected_sources": ["feature_scaling.pdf", "data_preprocessing.pdf"],
        "keywords": ["feature scaling", "normalization", "standardization", "min-max", "z-score"]
    },
    {
        "id": "q065",
        "query": "What is one-hot encoding?",
        "intent": "definitional",
        "complexity": "low",
        "ground_truth_answer": "One-hot encoding converts categorical variables into binary vectors. Each category becomes a binary column: 1 if present, 0 otherwise. Example: colors [red, blue, green] → [1,0,0], [0,1,0], [0,0,1]. For n categories, creates n binary features. Handles nominal data without imposing ordinal relationships. Issues: high dimensionality with many categories (use target encoding, hash encoding), dummy variable trap (drop one category to avoid multicollinearity in linear models). Alternatives: label encoding (ordinal data), target encoding (high cardinality), embedding layers (neural networks). Essential preprocessing step for most ML algorithms.",
        "relevant_doc_ids": ["doc_encoding_1089", "doc_categorical_variables_1001"],
        "expected_sources": ["categorical_encoding.pdf", "feature_engineering.pdf"],
        "keywords": ["one-hot encoding", "categorical variables", "dummy variables", "encoding"]
    },
    {
        "id": "q066",
        "query": "What is the curse of dimensionality?",
        "intent": "conceptual",
        "complexity": "high",
        "ground_truth_answer": "The curse of dimensionality refers to phenomena that arise when analyzing data in high-dimensional spaces. As dimensions increase: 1) Data becomes sparse (exponentially more volume), 2) Distance metrics become less meaningful (all points appear equidistant), 3) More data needed to maintain density, 4) Overfitting risk increases, 5) Computational cost grows exponentially. Affects: KNN, clustering, density estimation. Solutions: dimensionality reduction (PCA, t-SNE, UMAP), feature selection, regularization, domain knowledge for feature engineering. Particularly relevant for distance-based algorithms. Counter-intuitive: higher dimensions don't always mean better performance.",
        "relevant_doc_ids": ["doc_curse_dimensionality_1112", "doc_high_dim_data_1023"],
        "expected_sources": ["curse_of_dimensionality.pdf", "high_dimensional_analysis.pdf"],
        "keywords": ["curse of dimensionality", "high dimensions", "sparsity", "distance metrics", "overfitting"]
    },
    {
        "id": "q067",
        "query": "What is t-SNE?",
        "intent": "definitional",
        "complexity": "high",
        "ground_truth_answer": "t-SNE (t-Distributed Stochastic Neighbor Embedding) is a non-linear dimensionality reduction technique for visualization, typically reducing to 2D/3D. It preserves local structure by modeling pairwise similarities using probability distributions. Steps: 1) Compute pairwise similarities in high-dimensional space (Gaussian), 2) Compute similarities in low-dimensional space (Student's t-distribution), 3) Minimize KL divergence between distributions using gradient descent. Good for: visualization, finding clusters. Limitations: computationally expensive O(n²), non-deterministic (random initialization), doesn't preserve global structure, can't be applied to new data (no learned mapping). Hyperparameters: perplexity (5-50), learning rate, iterations.",
        "relevant_doc_ids": ["doc_tsne_1134", "doc_visualization_1045"],
        "expected_sources": ["tsne_explained.pdf", "dimensionality_reduction.pdf"],
        "keywords": ["t-SNE", "dimensionality reduction", "visualization", "manifold learning", "embedding"]
    },
    {
        "id": "q068",
        "query": "What is UMAP?",
        "intent": "definitional",
        "complexity": "high",
        "ground_truth_answer": "UMAP (Uniform Manifold Approximation and Projection) is a dimensionality reduction technique based on manifold learning and topological data analysis. Similar to t-SNE but faster and preserves more global structure. Uses Riemannian geometry and algebraic topology to model manifolds. Advantages over t-SNE: faster (can handle larger datasets), preserves global structure better, deterministic with fixed random seed, can transform new data. Hyperparameters: n_neighbors (local/global structure balance), min_dist (cluster tightness). Applications: visualization, preprocessing for ML, exploratory data analysis. Works well for clustering, general-purpose dimensionality reduction.",
        "relevant_doc_ids": ["doc_umap_1156", "doc_manifold_learning_1067"],
        "expected_sources": ["umap_guide.pdf", "modern_dimensionality_reduction.pdf"],
        "keywords": ["UMAP", "dimensionality reduction", "manifold learning", "visualization", "topology"]
    },
    {
        "id": "q069",
        "query": "How do I choose the right ML algorithm?",
        "intent": "procedural",
        "complexity": "medium",
        "ground_truth_answer": "Algorithm selection factors: 1) Task type: classification, regression, clustering, etc., 2) Data characteristics: size (small: linear models/trees, large: deep learning), dimensionality (high: regularization/dim reduction), structure (tabular: XGBoost/Random Forest, images: CNN, text: transformers, sequences: RNN/LSTM), 3) Requirements: interpretability (linear models, trees), speed (linear models, Naive Bayes), accuracy (ensembles, deep learning), 4) Data quality: clean (complex models), noisy (robust models like Random Forest). General recommendations: tabular data → XGBoost/Random Forest, images → CNNs, text → transformers, time series → LSTM/ARIMA. Start simple, iterate to complex. Always baseline with simple model.",
        "relevant_doc_ids": ["doc_algorithm_selection_1178", "doc_ml_guide_1089"],
        "expected_sources": ["algorithm_selection_guide.pdf", "practical_machine_learning.pdf"],
        "keywords": ["algorithm selection", "model choice", "machine learning", "best practices"]
    },
    {
        "id": "q070",
        "query": "What is A/B testing in machine learning?",
        "intent": "definitional",
        "complexity": "medium",
        "ground_truth_answer": "A/B testing compares two model versions to determine which performs better in production. Randomly assign users to variant A (control) or B (treatment), measure key metrics (accuracy, engagement, revenue), test for statistical significance. Steps: 1) Define hypothesis and success metrics, 2) Determine sample size and test duration, 3) Random user assignment, 4) Collect data, 5) Statistical analysis (t-test, chi-square), 6) Decision based on significance and practical impact. Considerations: multiple testing correction, novelty effects, seasonality, sufficient traffic. Used for: model updates, feature changes, UX improvements. Essential for data-driven decision making in ML deployment.",
        "relevant_doc_ids": ["doc_ab_testing_1201", "doc_experimentation_1112"],
        "expected_sources": ["ab_testing_guide.pdf", "online_experimentation.pdf"],
        "keywords": ["A/B testing", "experimentation", "statistical significance", "control", "treatment"]
    },
    {
        "id": "q071",
        "query": "What is model deployment?",
        "intent": "definitional",
        "complexity": "medium",
        "ground_truth_answer": "Model deployment is the process of integrating a trained ML model into production systems to make predictions on new data. Steps: 1) Model serialization (pickle, ONNX, SavedModel), 2) Create API/service (Flask, FastAPI, TensorFlow Serving), 3) Containerization (Docker), 4) Infrastructure setup (cloud, on-premise), 5) Monitoring and logging, 6) CI/CD pipeline. Deployment patterns: batch prediction (offline), real-time API (online), edge deployment (on-device). Challenges: latency requirements, scalability, model versioning, feature engineering consistency, monitoring model drift. Tools: MLflow, Kubernetes, AWS SageMaker, Azure ML, Google Vertex AI.",
        "relevant_doc_ids": ["doc_model_deployment_1223", "doc_mlops_1134"],
        "expected_sources": ["model_deployment.pdf", "mlops_guide.pdf"],
        "keywords": ["model deployment", "MLOps", "production", "API", "serving", "inference"]
    },
    {
        "id": "q072",
        "query": "What is model monitoring?",
        "intent": "definitional",
        "complexity": "medium",
        "ground_truth_answer": "Model monitoring tracks model performance and behavior in production to detect issues. Monitor: 1) Performance metrics: accuracy, latency, throughput, 2) Data drift: input distribution changes over time, 3) Concept drift: relationship between inputs and outputs changes, 4) Prediction drift: output distribution changes, 5) Data quality: missing values, outliers, schema changes, 6) System health: errors, memory, CPU. Techniques: statistical tests (KS test, PSI), reference dataset comparison, automated retraining triggers. Tools: Evidently, WhyLabs, AWS SageMaker Model Monitor. Essential for: maintaining model accuracy, catching bugs, informing retraining decisions. Set up alerts for significant drift.",
        "relevant_doc_ids": ["doc_model_monitoring_1245", "doc_drift_detection_1156"],
        "expected_sources": ["model_monitoring.pdf", "production_ml.pdf"],
        "keywords": ["model monitoring", "data drift", "concept drift", "production", "MLOps"]
    },
    {
        "id": "q073",
        "query": "What is data leakage?",
        "intent": "definitional",
        "complexity": "medium",
        "ground_truth_answer": "Data leakage occurs when information from outside the training dataset improperly influences model training, leading to overly optimistic results that don't generalize. Types: 1) Target leakage: features that wouldn't be available at prediction time (future information), 2) Train-test contamination: test data influences training (data preprocessing on combined data, overlapping samples). Examples: using future stock prices to predict current prices, fitting scaler on full dataset before splitting. Consequences: inflated validation scores, poor production performance. Prevention: proper train-test split before preprocessing, temporal validation for time series, careful feature engineering, understanding data generation process. Often subtle and hard to detect.",
        "relevant_doc_ids": ["doc_data_leakage_1267", "doc_ml_pitfalls_1178"],
        "expected_sources": ["data_leakage.pdf", "common_ml_mistakes.pdf"],
        "keywords": ["data leakage", "target leakage", "train-test contamination", "overfitting"]
    },
    {
        "id": "q074",
        "query": "What is the difference between online and offline learning?",
        "intent": "comparison",
        "complexity": "low",
        "ground_truth_answer": "Offline (batch) learning: train model on entire dataset at once, model fixed until retrained, suitable when data is static or changes slowly. Advantages: simpler, full dataset optimization. Disadvantages: can't adapt to new patterns, periodic retraining needed. Online (incremental) learning: model updates continuously as new data arrives, adapts to changing patterns. Advantages: handles data drift, memory efficient (don't need full dataset), real-time adaptation. Disadvantages: more complex, risk of catastrophic forgetting, harder to debug. Use cases: offline for static problems (image classification), online for streaming data (stock prediction, recommendation systems). Some algorithms support both (SGD, neural networks); others only offline (Random Forest, XGBoost).",
        "relevant_doc_ids": ["doc_learning_paradigms_1289", "doc_online_learning_1201"],
        "expected_sources": ["learning_types.pdf", "online_learning.pdf"],
        "keywords": ["online learning", "offline learning", "batch learning", "incremental learning", "streaming"]
    },
    {
        "id": "q075",
        "query": "What is Naive Bayes classifier?",
        "intent": "definitional",
        "complexity": "medium",
        "ground_truth_answer": "Naive Bayes is a probabilistic classifier based on Bayes' theorem with the 'naive' assumption that features are conditionally independent given the class. P(class|features) = P(features|class) * P(class) / P(features). Types: Gaussian (continuous features), Multinomial (count data, text), Bernoulli (binary features). Advantages: fast training and prediction, works well with high-dimensional data, performs surprisingly well despite independence assumption, requires small training data, handles missing values naturally. Disadvantages: independence assumption rarely holds, poor probability estimates (though classifications often correct). Common use: text classification, spam filtering, real-time prediction.",
        "relevant_doc_ids": ["doc_naive_bayes_1312", "doc_probabilistic_models_1223"],
        "expected_sources": ["naive_bayes.pdf", "bayesian_methods.pdf"],
        "keywords": ["Naive Bayes", "probabilistic classifier", "Bayes theorem", "independence assumption", "text classification"]
    },
    {
        "id": "q076",
        "query": "What is SVM (Support Vector Machine)?",
        "intent": "definitional",
        "complexity": "high",
        "ground_truth_answer": "SVM finds optimal hyperplane that maximizes margin between classes in feature space. Support vectors are data points closest to decision boundary. For non-linear problems, uses kernel trick to implicitly map data to higher-dimensional space. Kernels: linear, RBF (Gaussian), polynomial, sigmoid. Hyperparameters: C (regularization, margin hardness), gamma (RBF kernel width). Advantages: effective in high dimensions, memory efficient (uses support vectors only), versatile (different kernels). Disadvantages: slow on large datasets O(n³), sensitive to feature scaling, choosing right kernel is difficult, not probabilistic (use Platt scaling). Best for: binary classification, small-medium datasets, high-dimensional data.",
        "relevant_doc_ids": ["doc_svm_1334", "doc_kernel_methods_1245"],
        "expected_sources": ["svm_explained.pdf", "support_vector_machines.pdf"],
        "keywords": ["SVM", "support vector machine", "kernel", "margin", "hyperplane", "RBF"]
    },
    {
        "id": "q077",
        "query": "What is K-Nearest Neighbors (KNN)?",
        "intent": "definitional",
        "complexity": "low",
        "ground_truth_answer": "KNN is a lazy learning algorithm that classifies data based on k closest training examples in feature space. Classification: majority vote of k neighbors. Regression: average of k neighbors. Distance metrics: Euclidean, Manhattan, Minkowski. Choosing k: small k (low bias, high variance), large k (high bias, low variance), use cross-validation. Advantages: simple, no training phase, naturally handles multi-class, non-parametric. Disadvantages: slow prediction O(n), memory intensive (stores all data), sensitive to feature scaling, curse of dimensionality, imbalanced data issues. Improvements: weighted KNN, KD-trees for speedup. Works best with: small datasets, low dimensions, after feature scaling.",
        "relevant_doc_ids": ["doc_knn_1356", "doc_lazy_learning_1267"],
        "expected_sources": ["knn_algorithm.pdf", "instance_based_learning.pdf"],
        "keywords": ["KNN", "k-nearest neighbors", "lazy learning", "instance-based", "distance metric"]
    },
    {
        "id": "q078",
        "query": "What is cross-entropy loss?",
        "intent": "definitional",
        "complexity": "medium",
        "ground_truth_answer": "Cross-entropy loss measures the difference between predicted probability distribution and true distribution. For binary classification: -[y*log(p) + (1-y)*log(1-p)] where y is true label, p is predicted probability. For multi-class: -Σ y_i*log(p_i) where y_i is one-hot encoded label, p_i is predicted probability for class i. Also called log loss. Used with: softmax activation (multi-class), sigmoid activation (binary). Why it works: penalizes confident wrong predictions heavily, maximizes likelihood, smooth gradient for backpropagation. Common in: classification tasks, language modeling, any probabilistic prediction. Related: KL divergence, negative log likelihood.",
        "relevant_doc_ids": ["doc_loss_functions_1378", "doc_cross_entropy_1289"],
        "expected_sources": ["loss_functions.pdf", "classification_training.pdf"],
        "keywords": ["cross-entropy", "log loss", "classification loss", "softmax", "probability"]
    },
    {
        "id": "q079",
        "query": "What is the difference between MSE and MAE?",
        "intent": "comparison",
        "complexity": "low",
        "ground_truth_answer": "MSE (Mean Squared Error): average of squared differences, formula: Σ(y-ŷ)²/n. MAE (Mean Absolute Error): average of absolute differences, formula: Σ|y-ŷ|/n. Differences: MSE penalizes large errors more (quadratic), sensitive to outliers, differentiable everywhere, units are squared. MAE treats all errors equally (linear), robust to outliers, not differentiable at zero, same units as target. Use MSE when: large errors are particularly bad, data has few outliers, want smooth gradients. Use MAE when: all errors equally important, data has outliers, want interpretable metric in original units. RMSE (√MSE) combines benefits: same units, still penalizes large errors.",
        "relevant_doc_ids": ["doc_regression_metrics_1401", "doc_error_measures_1312"],
        "expected_sources": ["regression_metrics.pdf", "loss_functions.pdf"],
        "keywords": ["MSE", "MAE", "mean squared error", "mean absolute error", "regression", "loss"]
    },
    {
        "id": "q080",
        "query": "What is model ensembling?",
        "intent": "definitional",
        "complexity": "medium",
        "ground_truth_answer": "Model ensembling combines multiple models to create a stronger predictor. Methods: 1) Voting: majority vote (classification) or average (regression), 2) Weighted voting: assign weights based on individual model performance, 3) Stacking: train meta-model on base model predictions, 4) Blending: similar to stacking with holdout set. Benefits: reduces variance, improves accuracy, increases robustness, reduces overfitting risk. Requirements: diverse models (different algorithms, features, or hyperparameters) - similar models don't help. Considerations: increased complexity, slower prediction, harder debugging. Common in: Kaggle competitions, production systems requiring high accuracy. Ensemble of diverse weak learners often beats single strong learner.",
        "relevant_doc_ids": ["doc_ensembling_1423", "doc_model_combination_1334"],
        "expected_sources": ["ensemble_methods.pdf", "model_ensembling.pdf"],
        "keywords": ["ensemble", "model combination", "voting", "stacking", "blending", "meta-model"]
    },
    {
        "id": "q081",
        "query": "What is gradient boosting?",
        "intent": "conceptual",
        "complexity": "high",
        "ground_truth_answer": "Gradient boosting builds an ensemble by sequentially adding weak learners (usually shallow decision trees) that correct previous models' errors. Each new model fits the residual errors (negative gradients) of the combined ensemble. Process: 1) Start with simple model (often mean value), 2) Calculate residuals, 3) Train new tree to predict residuals, 4) Add to ensemble with learning rate (shrinkage), 5) Repeat. Hyperparameters: n_estimators, learning_rate (smaller = more robust, needs more trees), max_depth, min_samples_split. Variants: GBM, XGBoost (regularization, parallel), LightGBM (histogram-based, faster), CatBoost (categorical features). Benefits: high accuracy, feature importance. Challenges: can overfit, sensitive to outliers, sequential training (slow).",
        "relevant_doc_ids": ["doc_gradient_boosting_1445", "doc_boosting_methods_1356"],
        "expected_sources": ["gradient_boosting_explained.pdf", "advanced_ensembles.pdf"],
        "keywords": ["gradient boosting", "boosting", "residuals", "weak learners", "XGBoost", "ensemble"]
    },
    {
        "id": "q082",
        "query": "How do I handle categorical variables with high cardinality?",
        "intent": "procedural",
        "complexity": "medium",
        "ground_truth_answer": "High cardinality (many unique categories) solutions: 1) Target encoding: replace category with mean target value for that category (risk of overfitting - use smoothing, cross-validation), 2) Frequency encoding: replace with occurrence count/frequency, 3) Feature hashing: hash categories to fixed number of bins, 4) Embedding layers: learn dense representations (neural networks), 5) Group rare categories: combine infrequent categories into 'other', 6) Binary encoding: represent as binary bits (more compact than one-hot), 7) Leave-one-out encoding: variant of target encoding. Avoid one-hot encoding (too many features). For tree-based models: some (CatBoost) handle categorical features natively. Best choice depends on: algorithm, cardinality level, target relationship.",
        "relevant_doc_ids": ["doc_high_cardinality_1467", "doc_advanced_encoding_1378"],
        "expected_sources": ["categorical_encoding_advanced.pdf", "feature_engineering_guide.pdf"],
        "keywords": ["high cardinality", "categorical variables", "target encoding", "feature hashing", "embeddings"]
    },
    {
        "id": "q083",
        "query": "What is learning rate scheduling?",
        "intent": "definitional",
        "complexity": "medium",
        "ground_truth_answer": "Learning rate scheduling adjusts learning rate during training to improve convergence. Strategies: 1) Step decay: reduce by factor every N epochs, 2) Exponential decay: multiply by decay rate each epoch, 3) Cosine annealing: follows cosine curve, 4) Reduce on plateau: reduce when validation metric stops improving, 5) Warm restarts: periodically reset to high learning rate, 6) Cyclic learning rate: oscillate between bounds, 7) One-cycle policy: increase then decrease (super-convergence). Benefits: escape local minima, faster convergence, fine-tune in later epochs, better final performance. Start high (fast initial learning), end low (fine-tuning). Modern optimizers (Adam) have adaptive rates but scheduling still helps. Important hyperparameter for training deep networks.",
        "relevant_doc_ids": ["doc_lr_scheduling_1489", "doc_optimization_tricks_1401"],
        "expected_sources": ["learning_rate_scheduling.pdf", "training_optimization.pdf"],
        "keywords": ["learning rate", "scheduling", "decay", "warm restarts", "cosine annealing", "training"]
    },
    {
        "id": "q084",
        "query": "What is the difference between AI, machine learning, and deep learning?",
        "intent": "comparison",
        "complexity": "low",
        "ground_truth_answer": "AI (Artificial Intelligence): broadest term, any technique enabling computers to mimic human intelligence (includes rule-based systems, search algorithms, ML). Machine Learning: subset of AI, systems that learn from data without explicit programming (includes decision trees, SVM, neural networks). Deep Learning: subset of ML, uses multi-layer neural networks to automatically learn hierarchical features (CNNs, RNNs, transformers). Relationship: DL ⊂ ML ⊂ AI. Evolution: AI (1950s, rule-based) → ML (1980s-90s, statistical learning) → DL (2010s, neural networks with many layers). Deep learning revolutionized AI by achieving human-level performance on complex tasks (vision, language) but requires large data and compute.",
        "relevant_doc_ids": ["doc_ai_ml_dl_1512", "doc_field_overview_1423"],
        "expected_sources": ["ai_ml_dl_comparison.pdf", "artificial_intelligence_intro.pdf"],
        "keywords": ["AI", "machine learning", "deep learning", "artificial intelligence", "neural networks"]
    },
    {
        "id": "q085",
        "query": "What is model compression?",
        "intent": "definitional",
        "complexity": "high",
        "ground_truth_answer": "Model compression reduces model size and computational requirements while maintaining performance. Techniques: 1) Pruning: remove unimportant weights/neurons (magnitude-based, structured), 2) Quantization: reduce precision (FP32→INT8), 3) Knowledge distillation: train small student model to mimic large teacher, 4) Low-rank factorization: decompose weight matrices, 5) Weight sharing: use same weights for multiple connections. Benefits: faster inference, less memory, energy efficient, enables edge deployment. Trade-offs: slight accuracy loss, training complexity. Applications: mobile apps, edge devices, real-time systems. Tools: TensorFlow Lite, PyTorch Mobile, ONNX Runtime. Typical compression: 4-10x smaller with <1% accuracy loss.",
        "relevant_doc_ids": ["doc_model_compression_1534", "doc_efficient_ml_1445"],
        "expected_sources": ["model_compression.pdf", "efficient_deep_learning.pdf"],
        "keywords": ["model compression", "pruning", "quantization", "knowledge distillation", "mobile", "edge"]
    },
    {
        "id": "q086",
        "query": "What is knowledge distillation?",
        "intent": "conceptual",
        "complexity": "high",
        "ground_truth_answer": "Knowledge distillation trains a small student model to mimic a large teacher model's behavior. Teacher provides 'soft targets' (probability distributions) that contain more information than hard labels. Student learns from: 1) Soft targets from teacher (with temperature scaling to soften probabilities), 2) Hard ground truth labels, 3) Combined loss = α*distillation_loss + (1-α)*student_loss. Temperature parameter τ: higher τ creates softer probabilities. Benefits: smaller model, faster inference, similar accuracy to teacher, transfers dark knowledge (learned patterns). Applications: model compression, ensemble distillation, cross-architecture transfer. Variants: self-distillation, online distillation, multi-teacher. Achieves 1/10th size with ~95% of teacher's accuracy.",
        "relevant_doc_ids": ["doc_knowledge_distillation_1556", "doc_model_compression_methods_1467"],
        "expected_sources": ["knowledge_distillation.pdf", "model_compression_techniques.pdf"],
        "keywords": ["knowledge distillation", "teacher-student", "soft targets", "model compression", "transfer learning"]
    },
    {
        "id": "q087",
        "query": "What is federated learning?",
        "intent": "definitional",
        "complexity": "high",
        "ground_truth_answer": "Federated learning trains ML models across decentralized devices/servers holding local data, without exchanging raw data. Process: 1) Server sends initial model to devices, 2) Devices train on local data, 3) Devices send model updates (not data) to server, 4) Server aggregates updates (FedAvg: weighted average), 5) Server sends updated model back, 6) Repeat. Benefits: privacy preservation (data stays local), reduced communication (vs sending data), leverages edge compute. Challenges: heterogeneous data (non-IID), device availability, communication costs, security (Byzantine devices). Applications: smartphones (keyboard prediction), healthcare (medical records), finance. Variants: horizontal (same features, different users), vertical (same users, different features).",
        "relevant_doc_ids": ["doc_federated_learning_1578", "doc_distributed_ml_1489"],
        "expected_sources": ["federated_learning.pdf", "privacy_preserving_ml.pdf"],
        "keywords": ["federated learning", "decentralized", "privacy", "distributed training", "edge computing"]
    },
    {
        "id": "q088",
        "query": "What is the difference between parametric and non-parametric models?",
        "intent": "comparison",
        "complexity": "medium",
        "ground_truth_answer": "Parametric models: fixed number of parameters independent of dataset size (linear regression, logistic regression, neural networks). Assumptions about data distribution. Faster prediction, less memory, may not fit complex patterns if assumptions wrong. Non-parametric models: number of parameters grows with data size (KNN, decision trees, kernel SVM). More flexible, no strong distribution assumptions. Slower prediction, more memory, can model complex patterns, risk of overfitting. Examples: parametric (y=mx+b has 2 parameters regardless of data size), non-parametric (KNN stores all training data). Choice: parametric for simple patterns with assumptions, non-parametric for complex patterns without assumptions. Parametric = make assumptions, non-parametric = let data speak.",
        "relevant_doc_ids": ["doc_model_types_1601", "doc_parametric_nonparametric_1512"],
        "expected_sources": ["model_categorization.pdf", "statistical_learning.pdf"],
        "keywords": ["parametric", "non-parametric", "model types", "assumptions", "flexibility"]
    },
    {
        "id": "q089",
        "query": "How do I handle class imbalance in deep learning?",
        "intent": "procedural",
        "complexity": "medium",
        "ground_truth_answer": "Deep learning class imbalance solutions: 1) Class weights: penalize minority class errors more in loss function, 2) Focal loss: down-weights easy examples, focuses on hard ones, 3) Data augmentation: generate synthetic minority samples, 4) Oversampling: duplicate minority examples (use carefully to avoid overfitting), 5) Undersampling: reduce majority class, 6) Two-phase training: pretrain on balanced subset, fine-tune on full data, 7) Ensemble methods: train multiple models on balanced subsets, 8) Adjust decision threshold: optimize for F1 instead of accuracy. For extreme imbalance: consider anomaly detection approaches. Monitor precision/recall/F1, not accuracy. Combine multiple techniques for best results.",
        "relevant_doc_ids": ["doc_imbalance_dl_1623", "doc_class_imbalance_solutions_1534"],
        "expected_sources": ["deep_learning_imbalanced_data.pdf", "classification_challenges.pdf"],
        "keywords": ["class imbalance", "deep learning", "focal loss", "class weights", "oversampling"]
    },
    {
        "id": "q090",
        "query": "What is the attention mechanism's computational complexity?",
        "intent": "factual",
        "complexity": "high",
        "ground_truth_answer": "Standard self-attention has O(n²d) complexity where n is sequence length, d is embedding dimension. Breakdown: query-key dot products = O(n²d), softmax = O(n²), weighted sum of values = O(n²d). Memory: O(n²) for attention matrix. This is problematic for long sequences. Efficient variants: 1) Sparse attention: attend to subset of positions O(n√n), 2) Linear attention: kernelized attention O(nd²), 3) Longformer: sliding window + global attention O(n*w) where w is window size, 4) Performer: random feature maps O(nd²), 5) Flash Attention: I/O-aware algorithm, same complexity but faster. For n=1000, d=512: standard needs 1000²*512 = 512M operations. Efficiency critical for long documents, high-res images.",
        "relevant_doc_ids": ["doc_attention_complexity_1645", "doc_efficient_transformers_1556"],
        "expected_sources": ["transformer_efficiency.pdf", "attention_complexity_analysis.pdf"],
        "keywords": ["attention", "computational complexity", "self-attention", "efficiency", "O(n²)", "transformers"]
    },
    {
        "id": "q091",
        "query": "What is multi-task learning?",
        "intent": "definitional",
        "complexity": "medium",
        "ground_truth_answer": "Multi-task learning trains a single model on multiple related tasks simultaneously, sharing representations across tasks. Architecture: shared layers (bottom) + task-specific heads (top). Benefits: improved generalization (regularization effect), faster learning, data efficiency (leverage information across tasks), better representations. Works when: tasks are related, share common features, have similar domains. Loss: weighted sum of task losses. Challenges: task balancing (some tasks dominate), negative transfer (tasks interfere), choosing what to share. Applications: NLP (joint NER + POS tagging), vision (detection + segmentation), robotics (multiple skills). Related: transfer learning (sequential), multi-modal learning (different data types). Hard parameter sharing vs soft parameter sharing approaches.",
        "relevant_doc_ids": ["doc_multitask_learning_1667", "doc_task_sharing_1578"],
        "expected_sources": ["multi_task_learning.pdf", "joint_training.pdf"],
        "keywords": ["multi-task learning", "joint training", "task sharing", "shared representations"]
    },
    {
        "id": "q092",
        "query": "What is the difference between fine-tuning and feature extraction?",
        "intent": "comparison",
        "complexity": "medium",
        "ground_truth_answer": "Both use pre-trained models but differently. Feature extraction: freeze all pre-trained layers, only train new task-specific head. Faster, less data needed, prevents overfitting, preserves learned features. Use when: small dataset, task similar to pre-training task, limited compute. Fine-tuning: unfreeze some/all pre-trained layers, update weights on new task. Better performance, adapts features to new task, requires more data, risk of overfitting. Use when: larger dataset, task differs from pre-training, need maximum accuracy. Progressive fine-tuning: gradually unfreeze layers from top to bottom. Discriminative fine-tuning: different learning rates per layer (lower for early layers). General rule: feature extraction → fine-tuning as dataset size increases.",
        "relevant_doc_ids": ["doc_transfer_strategies_1689", "doc_pretrained_models_usage_1601"],
        "expected_sources": ["transfer_learning_strategies.pdf", "fine_tuning_vs_feature_extraction.pdf"],
        "keywords": ["fine-tuning", "feature extraction", "transfer learning", "pre-trained models", "freezing layers"]
    },
    {
        "id": "q093",
        "query": "What is catastrophic forgetting?",
        "intent": "definitional",
        "complexity": "high",
        "ground_truth_answer": "Catastrophic forgetting occurs when neural networks forget previously learned information upon learning new information. Particularly severe when training on sequential tasks. The model overwrites old weights to fit new data. Solutions: 1) Rehearsal: retain and replay old examples while learning new, 2) Regularization: constrain weight changes using importance (EWC - Elastic Weight Consolidation), 3) Dynamic architectures: add new neurons for new tasks, 4) Memory systems: separate short-term and long-term memory components, 5) Meta-learning: learn how to learn without forgetting. Applications: continual learning, lifelong learning, online learning. Challenge for: incremental class learning, domain adaptation, personalization. Different from overfitting which affects generalization, not memory.",
        "relevant_doc_ids": ["doc_catastrophic_forgetting_1712", "doc_continual_learning_1623"],
        "expected_sources": ["catastrophic_forgetting.pdf", "lifelong_learning.pdf"],
        "keywords": ["catastrophic forgetting", "continual learning", "lifelong learning", "sequential tasks", "memory"]
    },
    {
        "id": "q094",
        "query": "What are best practices for training deep neural networks?",
        "intent": "best_practices",
        "complexity": "medium",
        "ground_truth_answer": "Best practices: 1) Data: shuffle training data, normalize/standardize features, augment data, check for leakage, 2) Architecture: start simple then increase complexity, use batch normalization, add skip connections for deep networks, 3) Initialization: use He initialization (ReLU) or Xavier (tanh/sigmoid), 4) Optimization: use Adam optimizer initially, try SGD with momentum for final tuning, use learning rate scheduling, gradient clipping for RNNs, 5) Regularization: dropout, L2 regularization, early stopping, data augmentation, 6) Training: monitor both train and val loss, use tensorboard/logging, save checkpoints, 7) Debugging: overfit single batch first, check gradient flow, visualize activations. Start with proven architectures, iterate based on validation performance.",
        "relevant_doc_ids": ["doc_training_best_practices_1734", "doc_dl_cookbook_1645"],
        "expected_sources": ["deep_learning_best_practices.pdf", "neural_network_training_guide.pdf"],
        "keywords": ["best practices", "deep learning", "training", "optimization", "regularization", "debugging"]
    },
    {
        "id": "q095",
        "query": "How do I debug a model with poor validation but good training performance?",
        "intent": "troubleshooting",
        "complexity": "medium",
        "ground_truth_answer": "This indicates overfitting. Solutions: 1) Regularization: add dropout (0.2-0.5), increase L2 penalty, try L1 for feature selection, 2) Data: collect more training data, apply data augmentation, check for train-test distribution mismatch, 3) Model complexity: reduce layers/neurons, simplify architecture, increase dropout rate, 4) Training: implement early stopping, reduce training epochs, use cross-validation, 5) Batch normalization: can help generalization, 6) Ensemble: combine multiple models. Diagnostics: plot learning curves (train vs val loss over time), check if gap widens, analyze prediction errors. If validation was improving but degraded: use early stopping to restore best checkpoint. If never improved: data distribution mismatch or poor validation split.",
        "relevant_doc_ids": ["doc_overfitting_solutions_1756", "doc_troubleshooting_models_1667"],
        "expected_sources": ["debugging_overfitting.pdf", "model_troubleshooting_guide.pdf"],
        "keywords": ["overfitting", "debugging", "validation performance", "regularization", "troubleshooting"]
    },
    {
        "id": "q096",
        "query": "What is batch normalization and when should I use it?",
        "intent": "best_practices",
        "complexity": "medium",
        "ground_truth_answer": "Use batch normalization: 1) When: training deep networks (>10 layers), want faster convergence, experiencing vanishing/exploding gradients, 2) Where: after linear/conv layer, before or after activation (both work, before is standard), 3) Benefits: allows higher learning rates, reduces dependency on initialization, provides regularization, stabilizes training. Don't use when: very small batch sizes (<8), online learning (use Layer Norm instead), after dropout in same layer (redundant). Alternatives: Layer Normalization (for RNNs, transformers), Instance Normalization (style transfer), Group Normalization (small batches). During inference: uses running statistics from training, not batch statistics. Modern architectures (ResNet, Transformers) rely heavily on normalization for deep networks.",
        "relevant_doc_ids": ["doc_batch_norm_usage_1778", "doc_normalization_guide_1689"],
        "expected_sources": ["batch_normalization_guide.pdf", "normalization_techniques.pdf"],
        "keywords": ["batch normalization", "best practices", "when to use", "deep learning", "normalization"]
    },
    {
        "id": "q097",
        "query": "What is the difference between precision, recall, and F1 score?",
        "intent": "comparison",
        "complexity": "low",
        "ground_truth_answer": "Metrics for classification evaluation: Precision = TP/(TP+FP) - 'Of predicted positives, how many are correct?' Focus: minimizing false positives. Use when: false positives are costly (spam detection - don't want real emails marked spam). Recall = TP/(TP+FN) - 'Of actual positives, how many did we find?' Focus: minimizing false negatives. Use when: false negatives are costly (cancer detection - don't want to miss cases). F1 = 2*(Precision*Recall)/(Precision+Recall) - harmonic mean, balances both. Use when: need balance, class imbalance present. Trade-off: increasing precision often decreases recall. Choose based on business cost of errors. For imbalanced data: F1 or weighted F1 better than accuracy.",
        "relevant_doc_ids": ["doc_classification_metrics_detailed_1801", "doc_evaluation_guide_1712"],
        "expected_sources": ["classification_metrics_explained.pdf", "model_evaluation.pdf"],
        "keywords": ["precision", "recall", "F1 score", "classification metrics", "true positive", "false positive"]
    },
    {
        "id": "q098",
        "query": "How do I choose between L1 and L2 regularization?",
        "intent": "best_practices",
        "complexity": "medium",
        "ground_truth_answer": "Choose L1 (Lasso) when: need feature selection (produces sparse models with some weights exactly zero), have many irrelevant features, want interpretability (fewer features), high-dimensional data with suspicion many features irrelevant. Choose L2 (Ridge) when: all features potentially useful, features are correlated (handles multicollinearity better), want smooth weight shrinkage, don't need exact sparsity. Elastic Net: combines both, gets benefits of both, best when: many correlated features, need some sparsity, unsure which is better. Practical approach: try both, use cross-validation, check feature importance. Deep learning: L2 more common (weight decay), L1 less used (sparse neural networks research). For linear models: Lasso for feature selection, Ridge for prediction, Elastic Net for both.",
        "relevant_doc_ids": ["doc_regularization_selection_1823", "doc_l1_l2_guide_1734"],
        "expected_sources": ["choosing_regularization.pdf", "regularization_comparison.pdf"],
        "keywords": ["L1 regularization", "L2 regularization", "Lasso", "Ridge", "feature selection", "best practices"]
    },
    {
        "id": "q099",
        "query": "What is the purpose of a validation set?",
        "intent": "conceptual",
        "complexity": "low",
        "ground_truth_answer": "Validation set is a held-out dataset used during training to: 1) Tune hyperparameters (learning rate, regularization, architecture choices), 2) Perform model selection (choose best architecture), 3) Implement early stopping (monitor for overfitting), 4) Track training progress without touching test set. Typical split: 60-70% train, 15-20% validation, 15-20% test. Why not use test set? Would leak information, overfit to test performance. Workflow: train on training set, evaluate on validation set, iterate/tune, final evaluation on test set (once only). Cross-validation: when data is limited, use k-fold CV as validation strategy. Validation set prevents 'training' on test set through hyperparameter tuning. Essential for proper ML workflow and avoiding overly optimistic results.",
        "relevant_doc_ids": ["doc_validation_set_1845", "doc_train_test_split_1756"],
        "expected_sources": ["validation_strategies.pdf", "model_evaluation_workflow.pdf"],
        "keywords": ["validation set", "train-test split", "hyperparameter tuning", "overfitting", "model selection"]
    },
    {
        "id": "q100",
        "query": "When should I use deep learning vs traditional machine learning?",
        "intent": "best_practices",
        "complexity": "medium",
        "ground_truth_answer": "Use deep learning when: large dataset (>100K samples), unstructured data (images, text, audio, video), complex patterns (hierarchical features), end-to-end learning needed, sufficient compute resources available, state-of-the-art performance critical. Use traditional ML when: small dataset (<10K samples), tabular/structured data, need interpretability, limited compute, quick deployment needed, feature engineering is feasible. For tabular data: XGBoost/Random Forest often outperform neural networks with less effort. For images/text: deep learning (CNNs/transformers) is superior. Gray area (10K-100K samples): try both. Practical advice: start with simpler models, establish baseline, then try deep learning if needed. Deep learning requires: more data, more compute, more tuning, but can achieve better performance on complex tasks. Consider cost-benefit: is extra performance worth the complexity?",
        "relevant_doc_ids": ["doc_dl_vs_ml_1867", "doc_algorithm_selection_guide_1778"],
        "expected_sources": ["deep_learning_vs_traditional_ml.pdf", "when_to_use_deep_learning.pdf"],
        "keywords": ["deep learning", "traditional ML", "algorithm selection", "best practices", "tabular data", "images"]
    }
]

# Add remaining queries to dataset
dataset["queries"].extend(remaining_queries)

# Update metadata
dataset["metadata"]["total_queries"] = len(dataset["queries"])

# Write back to file
with open('test_dataset.json', 'w') as f:
    json.dump(dataset, f, indent=2)

print(f"Successfully added remaining queries. Total queries: {len(dataset['queries'])}")
