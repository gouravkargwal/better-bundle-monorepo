redis-cli XADD betterbundle:data-jobs "*" job_id "test_job_001" shop_id "shop_123" shop_domain "vnsaid.myshopify.com" access_token "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" job_type "data_collection" status "queued" timestamp "1756914634" worker_id "python-worker-1"


redis-cli XADD betterbundle:ml-training "*" job_id "ml_job_001" shop_id "shop_123" shop_domain "test-shop.myshopify.com" training_type "end_to_end" model_config '{"model_type": "recommendation", "hyperparameters": {"learning_rate": 0.01}}' timestamp "1756914634" worker_id "python-worker-1"


redis-cli XADD betterbundle:analysis-results "*" job_id "analytics_job_001" shop_id "shop_123" analytics_type "comprehensive_analysis" analysis_config '{"include_performance": true, "include_customer": true}' timestamp "1756914634" worker_id "python-worker-1"

redis-cli SET "gorse:training:complete:shop_123:model_rec_001" '{"status": "completed", "accuracy": 0.89, "completion_time": "2025-01-03T21:30:00Z"}'