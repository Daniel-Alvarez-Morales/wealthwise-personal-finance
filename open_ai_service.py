from config import OPENAI_API_KEY
from openai import OpenAI
import json

class OpenAIService:
    def __init__(self):
        print("🔧 Initializing OpenAI client...")
        try:
            self.client = OpenAI(api_key=OPENAI_API_KEY)
            print("✅ OpenAI client created successfully")
        except Exception as e:
            print(f"❌ Failed to create OpenAI client: {e}")
            raise

    def get_response(self, prompt):
        response = self.client.chat.completions.create(
            model="gpt-4.1-nano",
            max_tokens=512,
            n=1,
            messages=[{"role": "user", "content": prompt}]
        )
       
        return response.choices[0].message.content

    def get_responseByConversation(self, conversation_history):
        response = self.client.chat.completions.create(
            model="gpt-4.1-nano",
            max_tokens=512,
            n=1,
            messages=conversation_history
        )
        return response.choices[0].message.content

    def get_response_bank_statement(self, bank_statement):
        # Temporarily disabled - return empty string
        return ""
        
        # response = self.client.chat.completions.create(
        #     model="gpt-4.1-nano",
        #     max_tokens=512,
        #     n=1,
        #     messages=[{"role": "user", "content": "Analyze the following bank statement give a high level summary and then some trends and tips. \n\n" + bank_statement}]
        # )
       
        # return response.choices[0].message.content

    def categorize_transactions_ai(self, categories_json, uncategorized_transactions):
        """
        Use AI to categorize uncategorized transactions and update categories.json
        
        Args:
            categories_json (str): Current categories.json as string
            uncategorized_transactions (list): List of uncategorized transaction descriptions
            
        Returns:
            dict: Updated categories dictionary or None if AI couldn't categorize
        """
        print("🎯 ENTERING categorize_transactions_ai method")
        print(f"📊 Received {len(uncategorized_transactions)} transactions to categorize")
        print(f"📝 Categories JSON length: {len(categories_json)} characters")
        
        # Check if we have a valid API key
        try:
            api_key = self.client.api_key
            if api_key:
                print(f"🔑 API Key present: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else 'SHORT'}")
            else:
                print("❌ NO API KEY FOUND!")
                return None
        except Exception as e:
            print(f"❌ Error checking API key: {e}")
            return None
        prompt = f"""
You are a financial categorization expert. Analyze these uncategorized transactions and suggest NEW keywords to add to existing categories.

EXISTING CATEGORIES:
{json.dumps(list(json.loads(categories_json).keys()))}

UNCATEGORIZED TRANSACTIONS:
{uncategorized_transactions}

TASK: For each transaction, if it clearly matches an existing category (>80% confidence), extract ONLY the key merchant/service name.

RULES:
- Extract only merchant names (e.g., "MERCADONA", "ORANGE", "AMAZON")
- Skip transaction IDs, amounts, dates, card numbers, addresses
- Only suggest if very confident about category match
- Return ONLY new keywords to add, not the full categories

FORMAT: Return JSON with only categories that have NEW keywords to add:
{{
  "Groceries": ["MERCADONA", "LIDL"],
  "Utilities": ["ORANGE", "IBERDROLA"],
  "Amazon": ["Amazon.es"]
}}

Return ONLY the JSON with new keywords, no explanations:"""

        try:
            print("🌐 Making API call to OpenAI...")
            response = self.client.chat.completions.create(
                model="gpt-4.1-nano",
                max_tokens=4096,  # Further increased token limit for larger responses
                n=1,
                temperature=0.1,  # Lower temperature for more consistent results
                messages=[{"role": "user", "content": prompt}]
            )
            
            ai_response = response.choices[0].message.content.strip()
            print(f"📥 RAW AI RESPONSE:")
            print("=" * 60)
            print(ai_response)
            print("=" * 60)
            
            # Debug: Store the raw response for error reporting
            self.last_ai_response = ai_response
            
            # Clean the response - sometimes AI adds markdown formatting
            cleaned_response = ai_response
            if cleaned_response.startswith("```json"):
                print("🧹 Cleaning markdown JSON formatting...")
                cleaned_response = cleaned_response.replace("```json", "").replace("```", "").strip()
            elif cleaned_response.startswith("```"):
                print("🧹 Cleaning markdown formatting...")
                cleaned_response = cleaned_response.replace("```", "").strip()
            
            if cleaned_response != ai_response:
                print(f"🧹 CLEANED RESPONSE:")
                print("=" * 60)
                print(cleaned_response)
                print("=" * 60)
            
            # Try to parse the JSON response
            print("🔍 Attempting to parse JSON...")
            new_keywords_only = json.loads(cleaned_response)
            print(f"✅ JSON parsed successfully! Found {len(new_keywords_only)} categories with new keywords")
            
            # Merge new keywords with existing categories
            original_categories = json.loads(categories_json)
            updated_categories = original_categories.copy()
            
            # Console logging for successful categorization
            print("=" * 60)
            print("🤖 AI CATEGORIZATION RESULTS")
            print("=" * 60)
            print(f"✅ Successfully parsed AI response")
            print(f"📊 Categories with new keywords: {len(new_keywords_only)}")
            
            # Add new keywords to existing categories
            for category, new_keywords in new_keywords_only.items():
                if category in updated_categories:
                    # Add new keywords to existing category (avoid duplicates)
                    existing_keywords = updated_categories[category]
                    for keyword in new_keywords:
                        if keyword not in existing_keywords:
                            existing_keywords.append(keyword)
                    
                    print(f"📝 Category '{category}': Added {len(new_keywords)} new keywords")
                    for keyword in new_keywords:
                        print(f"   + '{keyword}'")
                else:
                    print(f"⚠️ Category '{category}' not found in existing categories, skipping")
            
            print("=" * 60)
            return updated_categories
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON DECODE ERROR: {str(e)}")
            print(f"🔍 Failed to parse response as JSON")
            # Store error details for Streamlit to access
            self.last_error = f"JSON Parse Error: {str(e)}"
            self.last_ai_response = ai_response if 'ai_response' in locals() else "No response received"
            return None
        except Exception as e:
            print(f"❌ API EXCEPTION: {str(e)}")
            print(f"🔍 Error type: {type(e).__name__}")
            # Store error details for Streamlit to access
            self.last_error = f"API Error: {str(e)}"
            self.last_ai_response = "API call failed"
            return None