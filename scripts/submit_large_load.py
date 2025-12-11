import requests
import json
import time

ALB_URL = "http://distributed-classifier-alb-2027736460.us-east-1.elb.amazonaws.com"
SUBMIT_ENDPOINT = f"{ALB_URL}/submit"

BASE_IMAGES = [
    "image1.jpg",
    "image10.jpg",
    "image11.jpg",
    "image12.jpeg",
    "image14.jpg",
    "image2.jpg",
    "image4.jpg",
    "image5.jpg",
    "image6.jpg",
    "image7.jpg",
    "image8.jpg",
    "image9.jpg"
]

TOTAL_IMAGES = 10

def submit_large_job():
    # Generate 30,000 keys by cycling through base images
    s3_keys = []
    for i in range(TOTAL_IMAGES):
        s3_keys.append(BASE_IMAGES[i % len(BASE_IMAGES)])
    
    payload = {
        "job_type": "image_classification",
        "s3_keys": s3_keys,
        "top_k": 1,
        "confidence_threshold": 0.5
    }

    print(f"Submitting job with {len(s3_keys)} images to {SUBMIT_ENDPOINT}...")
    
    try:
        start_time = time.time()
        response = requests.post(
            SUBMIT_ENDPOINT, 
            json=payload, 
            headers={"Content-Type": "application/json"}
        )
        end_time = time.time()
        
        print(f"Response Status: {response.status_code}")
        print(f"Time taken: {end_time - start_time:.2f} seconds")
        
        if response.status_code in [200, 202]:
            resp_json = response.json()
            print("Response Body:")
            print(json.dumps(resp_json, indent=2))
            
            job_id = resp_json.get("job_id") or resp_json.get("JobID")
            if job_id:
                print(f"\n[IMPORTANT] Job ID To Track: {job_id}")
        else:
            print("Error Response:")
            print(response.text)
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    submit_large_job()
