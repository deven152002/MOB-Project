from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import aiohttp
import json
from config import OLLAMA_ENDPOINT, OLLAMA_MODEL

class UserInteractionAgent(Agent):
    class InteractionBehaviour(CyclicBehaviour):
        async def generate_response(self, prompt):
            """Generate response using local Ollama instance"""
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                }
                try:
                    async with session.post(OLLAMA_ENDPOINT, json=payload) as response:
                        if response.status == 200:
                            result = await response.json()
                            return result.get('response', '')
                        else:
                            return f"Error: Received status code {response.status}"
                except Exception as e:
                    return f"Error communicating with Ollama: {str(e)}"

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg:
                print(f"Received message: {msg.body}")
                
                # Generate response using Ollama
                response = await self.generate_response(msg.body)
                
                # Send response back
                reply = Message(
                    to=str(msg.sender),
                    body=response,
                    metadata={"conversation_id": msg.metadata.get("conversation_id", "default")}
                )
                await self.send(reply)
                print(f"Sent response: {response}")
            else:
                print("No message received. Checking again...")

    async def setup(self):
        print(f"User Interaction Agent running with Ollama model: {OLLAMA_MODEL}")
        print(f"Endpoint: {OLLAMA_ENDPOINT}")
        self.add_behaviour(self.InteractionBehaviour())
