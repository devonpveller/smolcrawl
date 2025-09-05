@echo off
echo Chain test...

python use-cases\document-processing\doc_processor.py create-use-case --name chain-test --base-url http://localhost:1313 & echo "Step 1 done" & python use-cases\document-processing\doc_processor.py discover-urls --base-url http://localhost:1313 --save-urls chain_urls.txt & echo "Step 2 done" & python use-cases\document-processing\doc_processor.py full-pipeline --config use-cases\chain-test\config.json & echo "All done"

pause
