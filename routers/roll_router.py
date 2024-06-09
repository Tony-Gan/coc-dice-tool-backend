import json
import os
import re
import time
import random
import logging
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List

logging.basicConfig(filename='./logs/dice_tool.log', level=logging.ERROR, format='%(asctime)s:%(levelname)s:%(message)s', encoding='utf-8')

class DiceToolError(Exception):
    pass

class InvalidDiceTypeError(DiceToolError):
    pass

class InvalidModifierError(DiceToolError):
    pass

class SkillNotFoundError(DiceToolError):
    pass

class PCFileNotFoundError(DiceToolError):
    pass

class InvalidParameterError(Exception):
    pass

class DiceTool:
    mode = 1

    @staticmethod
    def roll_dice(command):
        valid_dice_types = {2, 3, 4, 6, 8, 10, 20, 100}
        pattern = re.compile(r'^\d*d\d+([+-]\d*d\d+|\d+)*$', re.IGNORECASE)

        if not pattern.match(command):
            raise InvalidDiceTypeError("输入指令无效，请点击“操作指引”获取帮助。")

        parts = re.split(r'([+-])', command)

        total = 0
        detailed_results = []
        current_operator = '+'

        for part in parts:
            if part in '+-':
                current_operator = part
            else:
                dice_match = re.match(r'(\d*)d(\d+)', part, re.IGNORECASE)
                static_match = re.match(r'(\d+)', part)
                if dice_match:
                    num_dice = int(dice_match.group(1)) if dice_match.group(1) else 1
                    dice_type = int(dice_match.group(2))
                    if dice_type not in valid_dice_types:
                        raise InvalidDiceTypeError(f"不存在这样的骰子哦：d{dice_type}。在这个维度中只存在以下这些骰子：{valid_dice_types}")
                    results = [random.randint(1, dice_type) for _ in range(num_dice)]
                    part_total = sum(results)
                    if current_operator == '-':
                        total -= part_total
                    else:
                        total += part_total
                    detailed_results.extend(results)
                elif static_match:
                    value = int(static_match.group(1))
                    if current_operator == '-':
                        total -= value
                        detailed_results.append(-value)
                    else:
                        total += value
                        detailed_results.append(value)

        return (command, total, detailed_results)

    @staticmethod
    def advanced_roll_dice(modifier):
        try:
            modifier = int(modifier)
        except ValueError:
            raise InvalidModifierError('不合法的修正数值，修正数值为奖励骰的数量减去惩罚骰的数量')
        
        if modifier > 10:
            modifier = 10
        elif modifier < -10:
            modifier = -10

        unit = random.randint(0, 9)
        tens_rolls = [random.randint(0, 9) for _ in range(1 + abs(modifier))]

        if modifier > 0:
            tens = min(tens_rolls)
        else:
            tens = max(tens_rolls)

        result = 10 * tens + unit
        if result == 0:
            result = 100

        if modifier > 0 and unit == 0 and tens == 0:
            result = 10 * min(tens_rolls) + unit
            if result == 0:
                result = 100

        return ("1d100", result, [f"{t}0 + {unit}" for t in tens_rolls])

    @staticmethod
    def pc_skill_roll(pc_number, skill_name, modifier=0):
        filename = f"./pcstats/pc_file{pc_number}.txt"
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                skills = {}
                for line in file:
                    name, value = line.strip().split('|')
                    skills[name.lower()] = int(value)
            if skill_name.lower() not in skills:
                raise SkillNotFoundError(f"技能“{skill_name}”未找到。")

            skill_value = skills[skill_name.lower()]
        except FileNotFoundError:
            raise PCFileNotFoundError(f"PC属性文件“{filename}”未找到。")

        roll_result = DiceTool.advanced_roll_dice(modifier)[1]
        success_level = DiceTool.calculate_success_level(skill_value, roll_result)

        return (skill_name, skill_value, roll_result, success_level)

    @staticmethod
    def secret_roll(command):
        dice_result = DiceTool.roll_dice(command)[1]

        tens_digit = (dice_result // 10) % 10
        units_digit = dice_result % 10

        if dice_result == 100:
            tens_digit = 0
            units_digit = 0
        random_digits = [random.randint(0, 9) for _ in range(12)]

        random_digits[2] = tens_digit
        random_digits[4] = units_digit

        secret_value = ''.join(map(str, random_digits))

        return secret_value

    @staticmethod
    def rival_roll(strict_mode, *args):
        rival_type = DiceTool.determine_rival_roll_type(args)
        player1_id = 'NPC1'
        player2_id = 'NPC2'
        pc1_skill_level = 0
        pc2_skill_level = 0
        pc1_skill_roll = 0
        pc2_skill_roll = 0
        pc1_success_level = ''
        pc2_success_level = ''
        if rival_type == 1:
            player1_id = int(args[0])
            skill1_name = args[1]
            player2_id = int(args[2])
            skill2_name = args[3]
            modifier1 = int(args[4]) if len(args) > 4 else 0
            modifier2 = int(args[5]) if len(args) > 5 else 0

            _, pc1_skill_level, pc1_skill_roll, pc1_success_level = DiceTool.pc_skill_roll(player1_id, skill1_name, modifier1)
            _, pc2_skill_level, pc2_skill_roll, pc2_success_level = DiceTool.pc_skill_roll(player2_id, skill2_name, modifier2)

        elif rival_type == 2:
            kp_skill = int(args[0]) if not args[2].isdigit() else int(args[2])
            player2_id = int(args[1]) if not args[2].isdigit() else int(args[0])
            skill2_name = args[2] if not args[2].isdigit() else args[1]
            if len(args) > 3:
                modifier1 = int(args[3]) if not args[2].isdigit() else int(args[4])
                modifier2 = int(args[4])  if not args[2].isdigit() else int(args[3])
            else:
                modifier1 = 0
                modifier2 = 0

            _, pc1_skill_roll, _ = DiceTool.advanced_roll_dice(modifier1)
            _, pc2_skill_level, pc2_skill_roll, pc2_success_level = DiceTool.pc_skill_roll(player2_id, skill2_name, modifier2)

            pc1_skill_level = kp_skill
            pc1_success_level = DiceTool.calculate_success_level(pc1_skill_level, pc1_skill_roll)

        elif rival_type == 3:
            kp_skill1 = int(args[0])
            kp_skill2 = int(args[1])
            modifier1 = int(args[2]) if len(args) > 2 else 0
            modifier2 = int(args[3]) if len(args) > 3 else 0

            _, pc1_skill_roll, _ = DiceTool.advanced_roll_dice(modifier1)
            _, pc2_skill_roll, _ = DiceTool.advanced_roll_dice(modifier2)

            pc1_skill_level = kp_skill1
            pc2_skill_level = kp_skill2
            
            pc1_success_level = DiceTool.calculate_success_level(pc1_skill_level, pc1_skill_roll)
            pc2_success_level = DiceTool.calculate_success_level(pc2_skill_level, pc2_skill_roll)

        else:
            raise InvalidParameterError("未识别的对抗类型。")
        
        success_type = ['大成功', '极限成功', '困难成功', '成功', '失败', '大失败']
        if strict_mode:
            if success_type.index(pc1_success_level) < success_type.index(pc2_success_level):
                winner = player1_id
            else:
                winner = player2_id
        else:
            if success_type.index(pc1_success_level) < success_type.index(pc2_success_level):
                winner = player1_id
            elif success_type.index(pc1_success_level) > success_type.index(pc2_success_level):
                winner = player2_id
            else:
                if pc1_skill_level > pc2_skill_level:
                    winner = player1_id
                elif pc1_skill_level < pc2_skill_level:
                    winner = player2_id
                else:
                    if pc1_skill_roll < pc2_skill_roll:
                        winner = player1_id
                    else:
                        winner = player2_id

        if rival_type == 1:
            return (player1_id, player2_id, skill1_name, skill2_name, pc1_skill_level, pc2_skill_level, pc1_skill_roll, pc2_skill_roll, pc1_success_level, pc2_success_level, winner)
        elif rival_type == 2:
            return (player2_id, skill2_name, pc1_skill_level, pc2_skill_level, pc1_skill_roll, pc2_skill_roll, pc1_success_level, pc2_success_level, winner)
        elif rival_type == 3:
            return (pc1_skill_level, pc2_skill_level, pc1_skill_roll, pc2_skill_roll, pc1_success_level, pc2_success_level, winner)
        
    @staticmethod
    def determine_rival_roll_type(args):
        if len(args) < 2 or len(args) > 6:
            raise InvalidParameterError("Invalid number of parameters for rival roll.")

        def is_int(val):
            try:
                int(val)
                return True
            except ValueError:
                return False
    
        if is_int(args[0]) and len(args) >= 4 and is_int(args[2]) and not is_int(args[1]) and not is_int(args[3]):
            return 1
        
        if is_int(args[0]) and is_int(args[1]) or (is_int(args[0]) and not is_int(args[1]) and is_int(args[2])):
            if len(args) == 2 or len(args) == 4:
                return 3
            elif len(args) == 3 or len(args) == 5:
                return 2
            else:
                raise InvalidParameterError("Invalid parameters for Type 2 or 3 rival roll.")

        raise InvalidParameterError("Could not determine the type of rival roll.")
    
    @staticmethod
    def sancheck(pc_number, success_san_loss, fail_san_loss=None):
        filename = f"./pcstats/pc_file{pc_number}.txt"
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                stats = {}
                for line in file:
                    name, value = line.strip().split('|')
                    stats[name.lower()] = int(value)

            if 'int' not in stats and fail_san_loss is not None:
                raise SkillNotFoundError("INT属性未找到。")

            int_value = stats.get('int', None)
        except FileNotFoundError:
            return
        if fail_san_loss is None:
            try:
                adjustment = int(success_san_loss)
            except ValueError:
                return
            stats['current_san'] = min(stats.get('current_san', stats.get('san', 0)) + adjustment, stats.get('san', 0))
            remaining_san = stats['current_san']
            if remaining_san < 0:
                remaining_san = 0
                stats['current_san'] = 0

            with open(filename, 'w', encoding='utf-8') as file:
                for key, value in stats.items():
                    file.write(f"{key}|{value}\n")

            return (success_san_loss, remaining_san)
        else:
            skill_name = 'int'
            roll_result, _, _, success_level = DiceTool.pc_skill_roll(pc_number, skill_name, 0)

            def parse_san_loss(san_loss):
                if 'd' in san_loss:
                    return DiceTool.roll_dice(san_loss)[1]
                else:
                    return int(san_loss)

            if success_level == "大成功":
                reduction = min([parse_san_loss(val.strip()) for val in success_san_loss.split('+')])
            elif success_level in ["极限成功", "困难成功", "成功"]:
                reduction = parse_san_loss(success_san_loss)
            else:
                reduction = parse_san_loss(fail_san_loss)

            remaining_san = stats.get('current_san', stats.get('san', 0)) - reduction
            if remaining_san < 0:
                remaining_san = 0

            stats['current_san'] = remaining_san

            with open(filename, 'w', encoding='utf-8') as file:
                for key, value in stats.items():
                    file.write(f"{key}|{value}\n")

            return (success_san_loss, fail_san_loss, int_value, success_level, roll_result, reduction, remaining_san)
        
    @staticmethod
    def hp_adjust(pc_number, adjustment):
        filename = f"./pcstats/pc_file{pc_number}.txt"
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                stats = {}
                for line in file:
                    name, value = line.strip().split('|')
                    stats[name.lower()] = int(value)

            if 'hp' not in stats:
                raise SkillNotFoundError("HP属性未找到。")

        except FileNotFoundError:
            return

        def parse_adjustment(adj):
            if 'd' in adj:
                sign = -1 if adj.startswith('-') else 1
                adj = adj.lstrip('+-')
                return sign * DiceTool.roll_dice(adj)[1]
            else:
                return int(adj)

        adjustment_value = parse_adjustment(adjustment)
        stats['current_hp'] = min(max(stats.get('current_hp', stats.get('hp', 0)) + adjustment_value, 0), stats.get('hp', 0))
        remaining_hp = stats['current_hp']

        with open(filename, 'w', encoding='utf-8') as file:
            for key, value in stats.items():
                file.write(f"{key}|{value}\n")

        return (adjustment, adjustment_value, remaining_hp)
    
    @staticmethod
    def get_stat(pc_number, stat_name):
        filename = f"./pcstats/pc_file{pc_number}.txt"
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                stats = {}
                for line in file:
                    name, value = line.strip().split('|')
                    stats[name.lower()] = int(value)

            if stat_name.lower() not in stats:
                return {
                    "stat_name": "属性未找到",
                    "stat_value": -1
                }

            stat_value = stats[stat_name.lower()]
        except FileNotFoundError:
            return {
                "stat_name": "文件未找到",
                "stat_value": -1
            }

        return (stat_name, stat_value)
    
    @staticmethod
    def calculate_success_level(skill_level, skill_roll):
        if skill_roll == 1:
            success_level = "大成功"
        elif (skill_level < 50 and skill_roll >= 96) or (skill_level >= 50 and skill_roll == 100):
            success_level = "大失败"
        elif skill_roll <= skill_level / 5:
            success_level = "极限成功"
        elif skill_roll <= skill_level / 2:
            success_level = "困难成功"
        elif skill_roll <= skill_level:
            success_level = "成功"
        else:
            success_level = "失败"
        return success_level

router = APIRouter()

class RollRequest(BaseModel):
    command: str
    a1: Optional[str] = None
    a2: Optional[str] = None
    a3: Optional[str] = None
    a4: Optional[str] = None
    a5: Optional[str] = None
    a6: Optional[str] = None
    ip: Optional[str] = None
    time: Optional[str] = None

class StatsUploadRequest(BaseModel):
    user_id: int
    stats: str
    create_new: bool = False

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        try:
            message_str = message.decode('utf-8') if isinstance(message, bytes) else message
            for connection in self.active_connections:
                await connection.send_text(message_str)
        except Exception as e:
            logging.error(f"Error broadcasting message: {str(e)}")

manager = ConnectionManager()

@router.post("/roll")
async def roll_dice(request: RollRequest):
    try:
        if request.command.lower() == 'r' and request.a1:
            result = DiceTool.roll_dice(request.a1.strip())
        elif request.command.lower() == 'rm' and request.a1:
            result = DiceTool.advanced_roll_dice(request.a1.strip())
        elif request.command.lower() == 'rd' and request.a1 and request.a2:
            if request.a3:
                try:
                    a3 = int(request.a3)
                except ValueError:
                    logging.error("不合法的修正数值，修正数值为奖励骰的数量减去惩罚骰的数量。")
                    raise HTTPException(status_code=400, detail="不合法的修正数值，修正数值为奖励骰的数量减去惩罚骰的数量。")
                result = DiceTool.pc_skill_roll(request.a1.strip(), request.a2.strip(), a3)
            else:
                result = DiceTool.pc_skill_roll(request.a1.strip(), request.a2.strip())
        elif request.command.lower() == 'rh' and request.a1:
            result = DiceTool.secret_roll(request.a1.strip())
        elif (request.command.lower() == 'rav' or request.command.lower() == 'ravs') and request.a1 and request.a2:
            args = [request.a1.strip(), request.a2.strip()]
            if request.a3:
                args.append(request.a3.strip())
                if request.a4:
                    args.append(request.a4.strip())
                    if request.a5:
                        args.append(request.a5.strip())
                        if request.a6:
                            args.append(request.a6.strip())

            if request.command.lower() == 'rav':
                result = DiceTool.rival_roll(False, *args)
            else:
                result = DiceTool.rival_roll(True, *args)
        elif request.command.lower() == 'sc' and request.a1 and request.a2:
            if request.a3:
                result = DiceTool.sancheck(request.a1.strip(), request.a2.strip(), request.a3.strip())
            else:
                result = DiceTool.sancheck(request.a1.strip(), request.a2.strip())
        elif request.command.lower() == 'hp' and request.a1 and request.a2:
            result = DiceTool.hp_adjust(request.a1.strip(), request.a2.strip())
        elif request.command.lower() == 'st' and request.a1 and request.a2:
            result = DiceTool.get_stat(request.a1.strip(), request.a2.strip())
        else:
            logging.error("无法识别命令，点击“操作指引”获取指令帮助。")
            raise HTTPException(status_code=400, detail="无法识别命令，点击“操作指引”获取指令帮助。")

        response_data = {
            "command": request.command,
            "result": result,
            "ip": request.ip,
            "time": request.time
        }

        result_json = json.dumps(response_data, ensure_ascii=False).encode('utf-8')
        await manager.broadcast(result_json)
        return response_data  # Return the complete response_data including IP and time
    except InvalidDiceTypeError as e:
        logging.error(f"Invalid dice type error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidModifierError as e:
        logging.error(f"Invalid modifier error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except SkillNotFoundError as e:
        logging.error(f"Skill not found error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except PCFileNotFoundError as e:
        logging.error(f"PC file not found error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidParameterError as e:
        logging.error(f"Invalid parameter error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except DiceToolError as e:
        logging.error(f"DiceTool error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        raise e  # Re-raise HTTP exceptions to be handled as usual
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=400, detail="无法识别命令，点击“操作指引”获取指令帮助。")

@router.post("/upload_stats")
async def upload_stats(request: StatsUploadRequest):
    try:
        if not (0 <= request.user_id <= 999):
            raise ValueError("用户ID取值范围为0-999")
        
        parsed_stats = parse_stats(request.stats)
        
        os.makedirs('./pcstats', exist_ok=True)
        file_name = f'./pcstats/pc_file{request.user_id}.txt'

        # Delete old files
        delete_old_files('./pcstats', 30 * 24 * 60 * 60)  # 30 days
        
        # Handle create new file option
        if request.create_new and os.path.exists(file_name):
            os.remove(file_name)
        
        existing_stats = {}
        if os.path.exists(file_name):
            with open(file_name, 'r', encoding='utf-8') as file:
                for line in file:
                    if '|' in line:
                        key, value = line.strip().split('|', 1)
                        existing_stats[key] = value

        for stat in parsed_stats:
            key, value = stat.split('|', 1)
            existing_stats[key] = value

        with open(file_name, 'w', encoding='utf-8') as file:
            for key, value in existing_stats.items():
                file.write(f"{key}|{value}\n")
        
        return {"status": "success"}
    except ValueError as ve:
        logging.error(f"ValueError: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logging.error(f"Error uploading stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload stats")

@router.get("/occupied_ids")
async def get_occupied_ids():
    try:
        files = os.listdir('./pcstats')
        occupied_ids = [int(f[7:-4]) for f in files if f.startswith('pc_file') and f.endswith('.txt')]
        return {"occupied_ids": occupied_ids}
    except Exception as e:
        logging.error(f"Error fetching occupied IDs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch occupied IDs")

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == 'ping':
                await websocket.send_text('pong')
            else:
                await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def parse_stats(stats: str):
    if not stats.startswith(".st "):
        raise ValueError("属性格式错误，应以.st 为开头，请遵循角色创建表中的格式或点击“操作指引”获取帮助")

    stats = stats[4:]  # Remove ".st " prefix
    pattern = re.compile(r"([a-zA-Z\u4e00-\u9fa5]+)(\d+)")
    matches = pattern.findall(stats)

    if not matches:
        raise ValueError("属性格式错误，请遵循角色创建表中的格式或点击“操作指引”获取帮助")

    parsed_stats = []
    for string, digit in matches:
        parsed_stats.append(f"{string}|{digit}")
        if string in ["san", "hp", "mp"]:
            parsed_stats.append(f"current_{string}|{digit}")

    return parsed_stats

def delete_old_files(directory: str, max_age_seconds: int):
    current_time = time.time()
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            file_age = current_time - os.path.getmtime(file_path)
            if file_age > max_age_seconds:
                os.remove(file_path)
                logging.info(f"Deleted old file: {file_path}")
