pipeline {
    agent any
    triggers {
        pollSCM('* * * * *')
    }
    stages {
        stage('Checkout') {
            steps { checkout scm }
        }
        stage('Setup') {
            steps {
                bat 'py -m venv .venv'
                bat '.venv\\Scripts\\python -m pip install --upgrade pip'
                bat '.venv\\Scripts\\python -m pip install -r requirements.txt'
                bat 'if not exist reports mkdir reports'
            }
        }
        stage('Lint') {
            steps { bat '.venv\\Scripts\\python -m flake8 app seed.py run.py || exit /b 0' }
        }
        stage('Security Scan') {
            steps { bat '.venv\\Scripts\\python -m bandit -r app || exit /b 0' }
        }
        stage('Unit Tests') {
            steps { bat '.venv\\Scripts\\python -m pytest -m unit -o addopts=-ra --junitxml=reports\\unit.xml' }
        }
        stage('Integration Tests') {
            steps { bat '.venv\\Scripts\\python -m pytest -m integration -o addopts=-ra --junitxml=reports\\integration.xml' }
        }
        stage('API Tests') {
            steps { bat '.venv\\Scripts\\python -m pytest -m api -o addopts=-ra --junitxml=reports\\api.xml' }
        }
        stage('Security Tests') {
            steps { bat '.venv\\Scripts\\python -m pytest -m security -o addopts=-ra --junitxml=reports\\security.xml' }
        }
        stage('Coverage') {
            steps {
                bat '.venv\\Scripts\\python -m pytest -o addopts=-ra --cov=app --cov-report=xml --cov-report=html --cov-fail-under=85 --junitxml=reports\\coverage.xml'
            }
        }
    }
    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/*.xml'
            archiveArtifacts allowEmptyArchive: true, artifacts: 'htmlcov/**'
        }
        success { echo 'ShopSphere pipeline completed successfully.' }
        failure { echo 'ShopSphere pipeline failed. Review the stage logs and test reports.' }
    }
}
