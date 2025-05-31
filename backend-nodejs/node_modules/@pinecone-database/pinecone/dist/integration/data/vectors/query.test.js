"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const index_1 = require("../../../index");
const test_helpers_1 = require("../../test-helpers");
let pinecone, serverlessIndex, recordIds;
beforeAll(async () => {
    pinecone = new index_1.Pinecone();
    if (!process.env.SERVERLESS_INDEX_NAME) {
        throw new Error('SERVERLESS_INDEX_NAME environment variable is not set');
    }
    const serverlessIndexName = process.env.SERVERLESS_INDEX_NAME;
    serverlessIndex = pinecone
        .index(serverlessIndexName)
        .namespace(test_helpers_1.globalNamespaceOne);
    recordIds = await (0, test_helpers_1.getRecordIds)(serverlessIndex);
});
// todo: add pod tests
describe('query tests on serverless index', () => {
    test('query by id', async () => {
        const topK = 4;
        if (recordIds) {
            if (recordIds.length > 0) {
                const idForQuerying = recordIds[0];
                const assertions = (results) => {
                    expect(results.matches).toBeDefined();
                    expect(results.matches?.length).toEqual(topK);
                    // Necessary to avoid could-be-undefined error for `usage` field:
                    if (results.usage) {
                        expect(results.usage.readUnits).toBeDefined();
                    }
                };
                await (0, test_helpers_1.assertWithRetries)(() => serverlessIndex.query({ id: idForQuerying, topK: 4 }), assertions);
            }
        }
    });
    test('query when topK is greater than number of records', async () => {
        const topK = 11; // in setup.ts, we seed the serverless index w/11 records
        if (recordIds) {
            const idForQuerying = recordIds[1];
            const assertions = (results) => {
                expect(results.matches).toBeDefined();
                expect(results.matches?.length).toEqual(11); // expect 11 records to be returned
                // Necessary to avoid could-be-undefined error for `usage` field:
                if (results.usage) {
                    expect(results.usage.readUnits).toBeDefined();
                }
            };
            await (0, test_helpers_1.assertWithRetries)(() => serverlessIndex.query({ id: idForQuerying, topK: topK }), assertions);
        }
    });
    test('with invalid id, returns empty results', async () => {
        const topK = 2;
        const assertions = (results) => {
            expect(results.matches).toBeDefined();
            expect(results.matches?.length).toEqual(0);
        };
        await (0, test_helpers_1.assertWithRetries)(() => serverlessIndex.query({ id: '12354523423', topK }), assertions);
    });
    test('query with vector and sparseVector values', async () => {
        const topK = 1;
        const assertions = (results) => {
            expect(results.matches).toBeDefined();
            expect(results.matches?.length).toEqual(topK);
            // Necessary to avoid could-be-undefined error for `usage` field:
            if (results.usage) {
                expect(results.usage.readUnits).toBeDefined();
            }
        };
        await (0, test_helpers_1.assertWithRetries)(() => serverlessIndex.query({
            vector: [0.11, 0.22],
            sparseVector: {
                indices: [32, 5],
                values: [0.11, 0.22],
            },
            topK,
        }), assertions);
    });
    test('query with includeValues: true', async () => {
        const queryVec = Array.from({ length: 2 }, () => Math.random());
        const sparseVec = {
            indices: [0, 1],
            values: Array.from({ length: 2 }, () => Math.random()),
        };
        const assertions = (results) => {
            expect(results.matches).toBeDefined();
            expect(results.matches?.length).toEqual(2);
            // Necessary to avoid could-be-undefined error for `usage` field:
            if (results.usage) {
                expect(results.usage.readUnits).toBeDefined();
            }
        };
        await (0, test_helpers_1.assertWithRetries)(() => serverlessIndex.query({
            vector: queryVec,
            sparseVector: sparseVec,
            topK: 2,
            includeValues: true,
            includeMetadata: true,
        }), assertions);
    });
});
//# sourceMappingURL=query.test.js.map