import axios from 'axios';

// Simple load tester - 25 requests per minute for 2 minutes
class SimpleLoadTester {
  constructor() {
    this.baseUrl = 'https://api.homosapieus.com';
    this.shareId = 'fSTA5pLXmUozMD6G'; // From your logs
    this.results = [];
  }

  async makeRequest(requestNum) {
    const message = "Hi"; // Just send "Hi" for every request
    const startTime = Date.now();

    try {
      const response = await axios.post(`${this.baseUrl}/api/shared/${this.shareId}/chat`, {
        message: message,
        sessionId: `session_test${requestNum}mbo74lc4`, // Similar pattern to your logs
        language: 'en',
        patientId: 'ed51f3e8-e87b-4731-bc93-cf57f7a55f9b' // From your logs
      }, {
        headers: { 'Content-Type': 'application/json' },
        timeout: 30000
      });

      const responseTime = Date.now() - startTime;
      console.log(`✅ Request ${requestNum}: ${responseTime}ms - ${response.status}`);
      
      this.results.push({
        request: requestNum,
        success: true,
        responseTime,
        status: response.status
      });

    } catch (error) {
      const responseTime = Date.now() - startTime;
      console.log(`❌ Request ${requestNum}: FAILED - ${error.message}`);
      
      this.results.push({
        request: requestNum,
        success: false,
        responseTime,
        error: error.message
      });
    }
  }

  async run() {
    console.log('🚀 Starting load test: 25 requests/minute for 2 minutes');
    console.log('📊 Total requests: 50');
    console.log('⏱️  Interval: 2.4 seconds between requests');
    console.log('');

    const totalRequests = 50; // 25 req/min * 2 minutes
    const intervalMs = 2400; // 60000ms / 25 requests = 2400ms

    for (let i = 1; i <= totalRequests; i++) {
      // Fire request without waiting
      this.makeRequest(i);
      
      // Wait before next request (except for last one)
      if (i < totalRequests) {
        await new Promise(resolve => setTimeout(resolve, intervalMs));
      }
    }

    // Wait a bit for last requests to complete
    console.log('\n⏳ Waiting for remaining requests...');
    await new Promise(resolve => setTimeout(resolve, 10000));

    this.showReport();
  }

  showReport() {
    const successful = this.results.filter(r => r.success).length;
    const failed = this.results.length - successful;
    const avgResponseTime = this.results
      .filter(r => r.success)
      .reduce((sum, r) => sum + r.responseTime, 0) / successful;

    console.log('\n📋 LOAD TEST RESULTS');
    console.log('====================');
    console.log(`Total Requests: ${this.results.length}`);
    console.log(`Successful: ${successful}`);
    console.log(`Failed: ${failed}`);
    console.log(`Success Rate: ${(successful/this.results.length*100).toFixed(1)}%`);
    console.log(`Average Response Time: ${avgResponseTime.toFixed(0)}ms`);
    console.log('\n💰 Now check your GCP billing console for Vertex AI costs!');
  }
}

// Run the test
const tester = new SimpleLoadTester();
tester.run().catch(console.error);

// To use this:
// 1. npm install axios
// 2. Make sure your package.json has "type": "module"
// 3. node load-test.js
// 
// Uses data from your logs:
// - shareId: fSTA5pLXmUozMD6G
// - patientId: ed51f3e8-e87b-4731-bc93-cf57f7a55f9b
// - Just sends "Hi" for every request