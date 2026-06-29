# Classical ML Fundamentals

AIF-C01 exam prep — Session 12. Covers all classical ML concepts tested on the AWS AI Practitioner cert: learning paradigms, common algorithms, evaluation metrics, overfitting/underfitting, and the bias-variance tradeoff. All run with real output on synthetic claim denial data.

## What it demonstrates

| Concept | Where |
|---------|-------|
| Supervised vs unsupervised learning | Sections 1, 8 |
| Train / validation / test split + stratify | Section 2 |
| Logistic regression + class imbalance fix | Section 3 |
| Confusion matrix — TP, TN, FP, FN | Section 3 |
| Accuracy, Precision, Recall, F1, AUC-ROC | Sections 3, 6 |
| Overfitting proof (unlimited decision tree) | Section 4 |
| Regularization (max_depth) | Section 4 |
| Random forest — ensemble, feature importance | Section 5 |
| ROC curve — two models compared | Section 6 |
| RMSE vs MAE — regression metrics | Section 7 |
| k-Means clustering — unsupervised | Section 8 |
| Elbow method — choosing k | Section 8 |
| Bias-variance tradeoff via cross-validation | Section 9 |

## Run

```bash
python ml-fundamentals/classical_ml_demo.py
```

No AWS credentials required — pure sklearn on synthetic data.

## Output

Three charts saved alongside the script:

| File | Shows |
|------|-------|
| `overfit_curve.png` | Training vs test accuracy as tree depth grows |
| `roc_curve.png` | ROC curves for logistic regression and random forest |
| `kmeans.png` | Member clusters (scatter) + elbow method for k selection |

## Dependencies

```
scikit-learn
matplotlib
numpy
```

All standard — no `requirements.txt` needed beyond what's already installed.
