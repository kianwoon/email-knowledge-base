# Knowledge Management Plan

Plan:

1. Frontend - Navigation ( Topliavbar.tsx ):

+ Add a new item to the navitems array.

+ Label: Use t( "navigation. knowledgeManagement') (we'll add this key later).
+ Path: /knowledge.

+ Icon: Choose a si

ble icon (e.g., FaDatabase, FaBrain, FaBoxes).

+ This item will automatically be visible only when isAuthenticated

true due to how App. tsx handles routing.

2. Frontend - Routing ( App. sx):

+ Add a new protected route definition within the <Routes> :
© sx Apply to it8n.ts

<Route
path="/knowledge"
element={ auth. isAuthenticated ? <KnowledgeManagementPage /> : <Navigate to='
Pp

7" replace /> }

‘+ Import the new KnowLedgeManagementPage component.

3. Frontend - Page Component ( frontend/src/pages /KnowLedgeNanagenentPage. tsx ):

+ Create this new file.

+ Implement a React functional component.

+ Use useTranslat ion to get the t function.

+ Add a main heading, e.g., <Heading>{t( *knowledgeManagement. title")}</Heading>.

+ Set up state variables (useState) to hold summary data for both collections (e.g., rawDataSummary, vectorDataSummary ) and loading/error states.
+ Use useEffect to fetch the summary data on component mount using new AP! functions (defined in the next step).

+ Display the summaries using appropriate Chakra UI components (e.9., SimpleGrid, Card, Stat, Text ). Use translation keys for labels like "Raw
Data Collection’, "Vector Data Collection", “Item Count", etc.

4. Frontend - API Client ( frontend/sre/api/knowledge.ts - New File):

+ Create this new file to handle knowledge base related API calls.
+ Define functions like getCollectionSummary(collectionName: ‘email_knowledge’ | ‘email_knowledge base’) .
+ These functions will call new backend endpoints (e.g., GET /api/knowledge/sunmary/{coUlectionName} )-

+ Define TypeScript interfaces for the expected summary response (e.g., { count: number; /x other potential stats */ }).

5. Backend - API Endpoint ( backend/app/routes/knowledge.py - New File):

6. Ba

7. Ba

+ Create this new file.

+ Define a FastAPI APrRouter .

+ Create a route like GET /sunmary/{collection_name}.

+ Use Depends(get_current_user) to ensure the user is authenticated.
+ Validate the collect ion_name path parameter.

+ Call anew service function to get the summary data from Qdrant.

ickend - Service Logic ( backend/app/services/knowLedge_service.py - New File or Update Exi
+ Create this new file or add functions to an existing service managing Qdrant interactions.

‘+ Implement a function fetch_collection_summary(collection_name: str, qdrant_client: QdrantClient) (or similar).
+ Use the qdrant_client. count (collection_name=collection_name) method to get the number of items.

+ Potentially add logic to fetch other summary stats if needed in the future (e.g., dimensionality, indexing status - though count is the primary
requirement for now).

+ Return the summary data (e.g., {"*count'

result. count} ).
ickend - Main App ( backend /app/main.py ):
‘+ Import the new knowledge router.

+ Include the router using app. include_router(knowledge. router, prefix="/knowledge", tags=

knowledge"]) -

8. Translations ( frontend/src/i18n/Locales/.../transLation.json ):

‘+ Add all new translation keys used in TopNavbar. tsx and KnowledgeManagementPage.tsx to both en/translation.json and cn/translation. jso
ne

Summary of Steps:

This plan covers adding the navigation link, creating the new page route and component, defining frontend AP! calls, implementing backend endpoints and
service logic to fetch collection summaries (initially just ite counts) from Qdrant, and adding the necessary translations.

Does

this plan look good to proceed with, starting with the frontend changes?
