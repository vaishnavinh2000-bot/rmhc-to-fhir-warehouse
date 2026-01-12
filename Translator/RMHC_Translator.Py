!pip install fhir.resources requests

import csv
import uuid
import json
import requests
from fhir.resources.patient import Patient
from fhir.resources.observation import Observation
from fhir.resources.bundle import Bundle, BundleEntry, BundleEntryRequest

# Public Server Endpoint (The "Warehouse") [3]
PUBLIC_SERVER_URL = "http://hapi.fhir.org/baseR4"

def translate_and_send_rmhc(csv_data):
    # Use DictReader for streaming ingestion to maintain low memory usage [6]
    reader = csv.DictReader(csv_data.splitlines())
    
    for row in reader:
        # Create a temporary UUID to link the Patient and Observation in one transaction [1]
        temp_patient_uuid = f"urn:uuid:{uuid.uuid4()}"
        
        # 1. Build the Patient Resource using RMHC demographic data [7]
        # Map 'Sex' (F/M) to FHIR gender codes (female/male) [7, 8]
        gender_map = {"F": "female", "M": "male"}
        
        patient = Patient(**{
            "resourceType": "Patient",
            "identifier": [{"system": "http://rmhc.org/sid/policy-id", "value": row['policy_id']}],
            "name": [{"text": row['Name']}],
            "gender": gender_map.get(row['Sex'], "unknown")
        })

        # 2. Build the Observation Resource for Fasting Blood Sugar (FBS) [7, 9]
        # Link to the patient via the temporary UUID [2]
        fbs_observation = Observation(**{
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "coding": [{"system": "http://loinc.org", "code": "1558-6", "display": "Fasting glucose"}]
            },
            "subject": {"reference": temp_patient_uuid},
            "valueQuantity": {
                "value": float(row['FBS']) if row['FBS'] and row['FBS'] != '#N/A' else None,
                "unit": "mg/dL",
                "system": "http://unitsofmeasure.org",
                "code": "mg/dL"
            }
        })

        # 3. Assemble into a Transaction Bundle for Atomicity [1, 10]
        # This ensures the Patient and Observation are created together or not at all [10]
        bundle = Bundle(**{
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "fullUrl": temp_patient_uuid,
                    "resource": patient,
                    "request": {"method": "POST", "url": "Patient"}
                },
                {
                    "resource": fbs_observation,
                    "request": {"method": "POST", "url": "Observation"}
                }
            ]
        })

        # 4. Transmission to the Public Server [11]
        headers = {"Content-Type": "application/fhir+json"}
        response = requests.post(PUBLIC_SERVER_URL, data=bundle.json(), headers=headers)
        
        if response.status_code == 200:
            print(f"Successfully sent Patient {row['policy_id']} and FBS Observation.")
        else:
            print(f"Failed to send {row['policy_id']}: {response.text}")

# Sample RMHC Data from your source [7]
rmhc_csv_content = """Last_visit_date,policy_id,Name,Sex,FBS,height,weight
7/2/2013,AND0010888,THIRAVIDAMANI,F,159,155,83
31/5/2013,AND0012586,v.manimaran,M,205.6,158,66
"""

# Run the translator
translate_and_send_rmhc(rmhc_csv_content)
