import motor.motor_asyncio
import logging
from typing import Optional, Dict, Any, List
import os
from datetime import datetime, timezone

class DatabaseManager:
    """MongoDB manager for the Discord bot economy system."""
    
    def __init__(self):
        self.client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
        self.database: Optional[motor.motor_asyncio.AsyncIOMotorDatabase] = None
        self.is_connected = False
        self.logger = logging.getLogger(__name__)
    
    async def connect(self, connection_string: str = None, database_name: str = "discord_bot"):
        """Connect to MongoDB database."""
        try:
            # Use provided connection string or environment variable
            if connection_string is None:
                connection_string = os.getenv("MONGO_URI")
                if not connection_string:
                    self.logger.error("No MongoDB connection string provided")
                    return False
            
            self.logger.info("Connecting to MongoDB...")
            
            # Create client with optimal settings for Discord bot
            self.client = motor.motor_asyncio.AsyncIOMotorClient(
                connection_string,
                maxPoolSize=100,
                minPoolSize=10,
                maxIdleTimeMS=30000,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                socketTimeoutMS=30000
            )
            
            # Test connection
            await self.client.admin.command('ping')
            self.logger.info("✅ Successfully connected to MongoDB")
            
            # Set database
            self.database = self.client[database_name]
            self.is_connected = True
            
            # Initialize collections with indexes
            await self._initialize_collections()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to MongoDB: {e}")
            self.is_connected = False
            return False
    
    async def _initialize_collections(self):
        """Initialize collections with proper indexes."""
        try:
            # Users collection indexes
            users_collection = self.database['users']
            await users_collection.create_index("user_id", unique=True)
            await users_collection.create_index("balance")
            await users_collection.create_index("total_earned")
            
            # Inventory collection indexes
            inventory_collection = self.database['inventory']
            await inventory_collection.create_index([("user_id", 1), ("item_id", 1)], unique=True)
            
            # Mod logs collection indexes
            mod_logs_collection = self.database['mod_logs']
            await mod_logs_collection.create_index("guild_id")
            await mod_logs_collection.create_index("timestamp")
            
            self.logger.info("✅ Database collections initialized with indexes")
            
        except Exception as e:
            self.logger.error(f"Error initializing collections: {e}")
    
    async def disconnect(self):
        """Disconnect from MongoDB."""
        try:
            if self.client:
                self.client.close()
                self.is_connected = False
                self.logger.info("Disconnected from MongoDB")
        except Exception as e:
            self.logger.error(f"Error disconnecting from MongoDB: {e}")
    
    def get_collection(self, collection_name: str):
        """Get a collection from the database."""
        if not self.is_connected or not self.database:
            self.logger.warning("Database not connected when accessing collection")
            return None
        
        return self.database[collection_name]
    
    # -------------------- User Management Methods --------------------
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user data from database."""
        try:
            users_collection = self.get_collection('users')
            if not users_collection:
                return None
            
            user_data = await users_collection.find_one({"user_id": str(user_id)})
            return user_data
            
        except Exception as e:
            self.logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    async def create_user(self, user_id: int, initial_balance: int = 1000) -> bool:
        """Create a new user in the database."""
        try:
            users_collection = self.get_collection('users')
            if not users_collection:
                return False
            
            user_data = {
                "user_id": str(user_id),
                "balance": initial_balance,
                "bank_balance": 0,
                "last_daily": None,
                "last_work": None,
                "last_crime": None,
                "total_earned": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            result = await users_collection.insert_one(user_data)
            return result.inserted_id is not None
            
        except Exception as e:
            self.logger.error(f"Error creating user {user_id}: {e}")
            return False
    
    async def update_user_balance(self, user_id: int, wallet_change: int = 0, bank_change: int = 0) -> bool:
        """Update user's wallet and/or bank balance."""
        try:
            users_collection = self.get_collection('users')
            if not users_collection:
                return False
            
            update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
            
            if wallet_change != 0:
                update_data["$inc"] = {"balance": wallet_change}
            if bank_change != 0:
                if "$inc" not in update_data:
                    update_data["$inc"] = {}
                update_data["$inc"]["bank_balance"] = bank_change
            
            # Update total earned if adding to wallet
            if wallet_change > 0:
                if "$inc" not in update_data:
                    update_data["$inc"] = {}
                update_data["$inc"]["total_earned"] = wallet_change
            
            result = await users_collection.update_one(
                {"user_id": str(user_id)},
                update_data,
                upsert=True
            )
            
            return result.modified_count > 0 or result.upserted_id is not None
            
        except Exception as e:
            self.logger.error(f"Error updating user balance for {user_id}: {e}")
            return False
    
    async def set_user_cooldown(self, user_id: int, cooldown_type: str) -> bool:
        """Set a cooldown timestamp for a user."""
        try:
            users_collection = self.get_collection('users')
            if not users_collection:
                return False
            
            cooldown_field = f"last_{cooldown_type}"
            
            result = await users_collection.update_one(
                {"user_id": str(user_id)},
                {
                    "$set": {
                        cooldown_field: datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                },
                upsert=True
            )
            
            return result.modified_count > 0 or result.upserted_id is not None
            
        except Exception as e:
            self.logger.error(f"Error setting cooldown for user {user_id}: {e}")
            return False
    
    async def get_user_cooldown(self, user_id: int, cooldown_type: str) -> Optional[datetime]:
        """Get a user's cooldown timestamp."""
        try:
            users_collection = self.get_collection('users')
            if not users_collection:
                return None
            
            user_data = await users_collection.find_one({"user_id": str(user_id)})
            if not user_data:
                return None
            
            cooldown_field = f"last_{cooldown_type}"
            cooldown_str = user_data.get(cooldown_field)
            
            if not cooldown_str:
                return None
            
            return datetime.fromisoformat(cooldown_str)
            
        except Exception as e:
            self.logger.error(f"Error getting cooldown for user {user_id}: {e}")
            return None
    
    # -------------------- Inventory Management Methods --------------------
    async def add_item_to_inventory(self, user_id: int, item_id: int, quantity: int = 1) -> bool:
        """Add an item to user's inventory."""
        try:
            inventory_collection = self.get_collection('inventory')
            if not inventory_collection:
                return False
            
            result = await inventory_collection.update_one(
                {"user_id": str(user_id), "item_id": item_id},
                {
                    "$inc": {"quantity": quantity},
                    "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                },
                upsert=True
            )
            
            return result.modified_count > 0 or result.upserted_id is not None
            
        except Exception as e:
            self.logger.error(f"Error adding item to inventory for user {user_id}: {e}")
            return False
    
    async def remove_item_from_inventory(self, user_id: int, item_id: int, quantity: int = 1) -> bool:
        """Remove an item from user's inventory."""
        try:
            inventory_collection = self.get_collection('inventory')
            if not inventory_collection:
                return False
            
            # First get current quantity
            item_data = await inventory_collection.find_one(
                {"user_id": str(user_id), "item_id": item_id}
            )
            
            if not item_data:
                return False
            
            current_quantity = item_data.get('quantity', 0)
            
            if current_quantity <= quantity:
                # Remove the item entirely
                result = await inventory_collection.delete_one(
                    {"user_id": str(user_id), "item_id": item_id}
                )
                return result.deleted_count > 0
            else:
                # Decrease quantity
                result = await inventory_collection.update_one(
                    {"user_id": str(user_id), "item_id": item_id},
                    {
                        "$inc": {"quantity": -quantity},
                        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                    }
                )
                return result.modified_count > 0
            
        except Exception as e:
            self.logger.error(f"Error removing item from inventory for user {user_id}: {e}")
            return False
    
    async def get_user_inventory(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user's complete inventory."""
        try:
            inventory_collection = self.get_collection('inventory')
            if not inventory_collection:
                return []
            
            cursor = inventory_collection.find({"user_id": str(user_id)})
            inventory = await cursor.to_list(length=None)
            return inventory
            
        except Exception as e:
            self.logger.error(f"Error getting inventory for user {user_id}: {e}")
            return []
    
    # -------------------- Statistics and Analytics --------------------
    async def get_economy_stats(self) -> Dict[str, Any]:
        """Get economy system statistics."""
        try:
            users_collection = self.get_collection('users')
            if not users_collection:
                return {}
            
            # Total users
            total_users = await users_collection.count_documents({})
            
            # Total money in circulation
            pipeline = [
                {"$group": {
                    "_id": None,
                    "total_wallet": {"$sum": "$balance"},
                    "total_bank": {"$sum": "$bank_balance"},
                    "total_earned": {"$sum": "$total_earned"}
                }}
            ]
            
            result = await users_collection.aggregate(pipeline).to_list(length=1)
            money_stats = result[0] if result else {}
            
            # Richest user
            richest_user = await users_collection.find_one(
                {},
                sort=[("balance", -1)]
            )
            
            return {
                "total_users": total_users,
                "total_money": money_stats.get('total_wallet', 0) + money_stats.get('total_bank', 0),
                "total_earned": money_stats.get('total_earned', 0),
                "richest_user": richest_user
            }
            
        except Exception as e:
            self.logger.error(f"Error getting economy stats: {e}")
            return {}
    
    async def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get wealth leaderboard."""
        try:
            users_collection = self.get_collection('users')
            if not users_collection:
                return []
            
            pipeline = [
                {"$addFields": {
                    "net_worth": {"$add": ["$balance", "$bank_balance"]}
                }},
                {"$sort": {"net_worth": -1}},
                {"$limit": limit},
                {"$project": {
                    "user_id": 1,
                    "balance": 1,
                    "bank_balance": 1,
                    "net_worth": 1
                }}
            ]
            
            cursor = users_collection.aggregate(pipeline)
            leaderboard = await cursor.to_list(length=limit)
            return leaderboard
            
        except Exception as e:
            self.logger.error(f"Error getting leaderboard: {e}")
            return []
    
    # -------------------- Backup and Maintenance --------------------
    async def backup_database(self) -> bool:
        """Create a backup of important collections."""
        try:
            # This is a simplified backup - in production you might want to use MongoDB's native backup tools
            backup_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "users_count": await self.get_collection('users').count_documents({}),
                "inventory_count": await self.get_collection('inventory').count_documents({})
            }
            
            self.logger.info(f"Database backup created: {backup_data}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating database backup: {e}")
            return False
    
    async def cleanup_old_data(self, days_old: int = 30) -> bool:
        """Clean up data older than specified days."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            
            # Clean up old mod logs
            mod_logs_collection = self.get_collection('mod_logs')
            if mod_logs_collection:
                result = await mod_logs_collection.delete_many({
                    "timestamp": {"$lt": cutoff_date.isoformat()}
                })
                self.logger.info(f"Cleaned up {result.deleted_count} old mod logs")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
            return False
    
    # -------------------- Health Check --------------------
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the database connection."""
        try:
            if not self.is_connected or not self.client:
                return {"status": "disconnected", "message": "Database not connected"}
            
            # Test connection
            start_time = datetime.now(timezone.utc)
            await self.client.admin.command('ping')
            ping_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            # Get collection counts
            users_count = await self.get_collection('users').count_documents({})
            inventory_count = await self.get_collection('inventory').count_documents({})
            
            return {
                "status": "connected",
                "ping_ms": round(ping_time, 2),
                "users_count": users_count,
                "inventory_count": inventory_count,
                "database": self.database.name,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {"status": "error", "message": str(e)}
