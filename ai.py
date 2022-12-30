
from chess import *
from evaluate_const import *
import random

def _knight_blocker(king: Square, knight: Square) -> Bitboard:
    masks = [BB_KNIGHT_REVERSED_MASKS[king] & ~BB_SQUARES[king + 15],
             BB_KNIGHT_REVERSED_MASKS[king] & ~BB_SQUARES[king + 17],
             BB_KNIGHT_REVERSED_MASKS[king] & ~BB_SQUARES[king - 15],
             BB_KNIGHT_REVERSED_MASKS[king] & ~BB_SQUARES[king - 17],
             ]
    for mask in masks:
        if BB_KNIGHT_REVERSED_ATTACKS[king][mask] & BB_SQUARES[knight]:
            return BB_KNIGHT_REVERSED_MASKS[king] & ~mask
    return BB_EMPTY


#Zobrist哈希算法随机量
zobrist=[[[random.randint(0,(1<<64)-1) for i in range(256)] for j in range(0,8)]for i in range(2)]
const_zobrist = random.randint(0,(1<<64)-1)     


#搜索相关默认值
Index_max = (1<<26)-1
default_depth = 6
alpha_win_value = 0x3f00
beta_win_value = -0x3f00


#   为适配Gui接口，这里建立类来封装所需方法与属性
class Searcher:

#   根据提前建立的棋子子力表,获取此选中棋子的子力值,用于局势评估
#   该棋子子力表综合考虑了棋子子力和棋子位置,从而缩减运算
#   由于象棋具有对称性，这里将黑方棋子子力设为正值，故其在搜素树中对应Max结点
#   而相应,红方在搜素树中对应Min结点,其棋子子力为负值
#   同时,红方与黑方用bool值表示，红方对应True，黑方对应False
    def value_square(self,square: Square,piece: Piece) -> int:   #Square为棋子在棋盘的序号，Piece为自定义类,
        if(piece == None): return 0                         #用与保存棋子类型与颜色,如果该位置没有棋子,返回0
        return self.pst[piece.color][piece.piece_type][square]                #否则正常返回棋子子力

    #返回棋子对应的zobrist值
    def key_square(self,square: Square,piece: Piece) -> None:  
        if(piece == None): return 0
        return zobrist[piece.color][piece.piece_type][square]

    #用于排序，返回某个移动在历史表中的得分的负值
    def sort_keys(self,move:Move) -> int:                          
        return -self.history[(move.from_square<<8) |move.to_square] #排序后得分大的排前面

    #尝试将当前局面存在置换表中
    def save_key(self,depth: int,value: int) -> None:
        index = self.key & Index_max
        #通过与操作获取哈希值对应的键值
        if (not (index in self.hash)) or self.hash[index]&7 >= depth:
            score = value	#采取深度优先规则，在具有键值时优先保存离根节点近的状态
            #由于当绝杀时返回的分数应与深度有关，故存储时应相应进行调整
            if score >= alpha_win_value:
                score += depth
            elif score <= beta_win_value:
                score -= depth

            tmp = (((((self.key<<12)|self.score)<<1)|self.turn)<<12)|score
            tmp = ((tmp<<8)|self.move.from_square)<<8|self.move.to_square
            self.hash[index] = (tmp<<3)|depth
    
    #位运算压缩表示，hash表项各部分位对应的值如下，其中前77位为校验值，用于区分是否为相同局面
    #64     12    1    12      8    8     3   
    #key  score flag  value  from   to   depth 

    #尝试从置换表中获取当前局面
    def load_key(self):
        index = self.key & Index_max
        if (index in self.hash) and (((((self.key<<12)|self.score)<<1)|self.turn) == (self.hash[index]>>31)):
            return self.hash[index]
        return None

    #模拟一次行动Move后的absearch搜素中后继状态的返回值
    def get_score(self,depth: int,lim_depth: int,beta: int,alpha: int,move: Move) -> int:
        #模拟移动
        to_piece = self.remove_piece_at(move.to_square)#类方法,通过棋子在棋盘的序号,移除该棋子并获取该棋子的类型Piece
        from_piece = self.remove_piece_at(move.from_square)
        self.set_piece_at(move.to_square,from_piece)   #类方法,在选定序号中放置选定的棋子
        #获取移动Move对局面价值的贡献,其通过先减掉初位置和末位置(如果有的话)的原有棋子子力值,然后加初位置棋子在末位置的棋子子力获取
        tmp_score = self.value_square(move.to_square,from_piece) - self.value_square(move.from_square,from_piece) - self.value_square(move.to_square,to_piece)

        #获取移动Move对哈希值的改变,其通过初位置和末位置(如果有的话)的原有棋子zobrist值与初位置棋子在末位置时的zobrist值同一常量异或获取
        tmp_key = self.key_square(move.to_square,from_piece) ^ self.key_square(move.from_square,from_piece) ^ self.key_square(move.to_square,to_piece) ^ const_zobrist
        #更新移动后局面评估值同时交换下棋方
        self.score += tmp_score
        self.key ^= tmp_key
        self.turn ^= 1

        #获取后继状态的返回值
        score = self.absearch(depth + 1,lim_depth,beta,alpha)

        #撤销移动
        self.turn ^= 1
        self.score -= tmp_score
        self.key ^= tmp_key
        self.set_piece_at(move.to_square,to_piece)
        self.set_piece_at(move.from_square,from_piece)

        return score



    #alpha-beta搜索的主体函数
    def absearch(self,depth: int,lim_depth: int,beta: int,alpha: int) -> int:
        self.num = self.num + 1

        #如果达到深度限制则返回当前局势评估值
        if(depth == lim_depth):
            return self.score
        tmp_move = None #保存当前的最佳移动
        tmp_score = 0x3fff if self.turn else -0x3fff
        index = self.load_key()
        if(index):
            tmp_depth,index = index & 7,index>>3
            to_square,index = index & 0xff,index>>8
            from_square,index = index & 0xff,index>>8
            score = index & 0xfff
            if score >= alpha_win_value:
                score -= depth
            elif score <= beta_win_value:
                score += depth
            
            #只有当已保存的局势更靠近根节点且使用该值发生截断时保存的值才有意义(因此要求不为根节点)
            #否则无法保证该移动是当前局势最优的
            if 0 < tmp_depth <= depth and ((not self.turn and score >= beta) or (self.turn and score <= alpha)):
                return score
            #但好的着法永远能做为当前局势的参考
            tmp_move = Move(from_square, to_square)
            tmp_score = self.get_score(depth,lim_depth,beta,alpha,tmp_move)
            if(self.turn and tmp_score < beta):
                self.move = tmp_move
                beta = tmp_score              #任何时候都有beta <= tmp_score
                if(beta <= alpha):        #符合条件时发生beta剪枝
                    self.history[(tmp_move.from_square<<8) |tmp_move.to_square] += (lim_depth - depth-1)**2
                    #维护历史表，给好的走法一个关于深度的增量，经测试后选择深度平方
                    self.save_key(depth,tmp_score)
                    #维护置换表
                    return tmp_score
            elif (not self.turn) and tmp_score > alpha:
                self.move = tmp_move
                alpha = tmp_score
                if(beta <= alpha):       #符合条件时发生alpha剪枝
                    self.history[(tmp_move.from_square<<8) |tmp_move.to_square] += (lim_depth - depth-1)**2
                    #维护历史表，给好的走法一个关于深度的增量，经测试后选择深度平方
                    self.save_key(depth,tmp_score)
                    #维护置换表
                    return tmp_score

        move_list = []
        for move in self.generate_legal_moves():    #类方法，获取当前所有合法的移动
            move_list.append(move)
        move_list.sort(key = self.sort_keys) #根据历史表降序排列

        if(self.turn):  #如果turn值为真，则其为红方，对应Min结点
            for move in move_list:    
                score = self.get_score(depth,lim_depth,beta,alpha,move)
                if(score < tmp_score or tmp_move == None):  
                    #如果此次移动优于之前移动或为初次移动,则更新临时值
                    tmp_move = move                      
                    tmp_score = score
                    if(score < beta):             #如果当前值小于beta值,则更新beta值
                        beta = score              #任何时候都有beta <= tmp_score
                        if(beta <= alpha):        #符合条件时发生beta剪枝
                            break
        else:
            for move in move_list:    
                score = self.get_score(depth,lim_depth,beta,alpha,move)
                if(score > tmp_score or tmp_move == None):
                    tmp_move = move
                    tmp_score = score  
                    if(score > alpha):          #如果当前值大于alpha值,则更新alpha值
                        alpha = score
                        if(beta <= alpha):       #符合条件时发生alpha剪枝
                            break

        self.move = tmp_move
        if(tmp_move == None):						#如果无路可走，说明被将死，此时返回最小值+深度，从而减少ai搜索到
            return tmp_score + (-depth if self.turn else depth)		        #杀招的深度
        else:
            self.history[(tmp_move.from_square<<8) |tmp_move.to_square] += (lim_depth - depth-1)**2
            #维护历史表，给好的走法一个关于深度的增量，经测试后选择深度平方
            self.save_key(depth,tmp_score)
            #维护置换表
        return tmp_score



    #alpha-beta搜索的入口函数，用于适配Gui接口，其从当前局势开始搜索并返回最佳移动与搜索状态数
    #默认深度设为6层
    def search(self,think_time: int,depth: int = default_depth):
        self.num = 0
        self.move = None
        self.absearch(0,depth,0x3fff,-0x3fff)

        return self.move,self.num


#以下为类的相关方法,基本算是为棋盘逻辑部分chess.py中的一个子集,用于辅助搜索算法
#这里不进行展示

    def __init__(self) -> None:
        self.occupied_co = [BB_EMPTY, BB_EMPTY]
        self.history = [0 for i in range(256*256)]
        self.ucvlPawnPiecesAttacking = [0 for _ in range(256)]
        self.ucvlPawnPiecesAttackless = [0 for _ in range(256)]
        self.pst = [[[0 for _ in range(256)] for _ in range(8)] for _ in range(2)]
        self.vlHollowThreat = [0 for _ in range(16)]
        self.vlCentralThreat = [0 for _ in range(16)]
        self.vlRedBottomThreat = [0 for _ in range(16)]
        self.vlBlackBottomThreat = [0 for _ in range(16)]
        self.hash = {}
        



    


    def set(self,board: BaseBoard,turn: bool) -> None:
        self.pawns = board.pawns
        self.knights = board.knights
        self.bishops = board.bishops
        self.rooks = board.rooks
        self.cannons = board.cannons
        self.advisors = board.advisors
        self.kings = board.kings
        self.turn = turn
        
        self.occupied_co[RED] = board.occupied_co[RED]
        self.occupied_co[BLACK] = board.occupied_co[BLACK]
        self.occupied = board.occupied
        self.key = const_zobrist if self.turn else 0
        self.score = self.evaluate_init()



    def reset(self) -> None:
        self.history = {}

    #用于生成子力表，其根据当前局势动态调整
    def evaluate_init(self) -> int:
        nMidgameValue = 6 * count_ones(self.rooks)
        for piece in (self.advisors,self.bishops,self.pawns):
            nMidgameValue += count_ones(piece)
        for piece in (self.knights,self.cannons):
            nMidgameValue += 3 * count_ones(piece)
        nMidgameValue = (2 * 66 - nMidgameValue) * nMidgameValue // 66
        for sq in range(256):
            if (cucvlKnightEndgame[sq]) :
                self.pst[BLACK][KING][sq] = (cucvlKingPawnMidgameAttacking[sq] * nMidgameValue + cucvlKingPawnEndgameAttacking[sq] * (66 - nMidgameValue)) // 66
                self.pst[BLACK][KNIGHT][sq] = (cucvlKnightMidgame[sq] * nMidgameValue + cucvlKnightEndgame[sq] * (66 - nMidgameValue)) // 66
                self.pst[BLACK][ROOK][sq] =  (cucvlRookMidgame[sq] * nMidgameValue + cucvlRookEndgame[sq] * (66 - nMidgameValue)) // 66
                self.pst[BLACK][CANNON][sq] =  (cucvlCannonMidgame[sq] * nMidgameValue + cucvlCannonEndgame[sq] * (66 - nMidgameValue)) //66
                self.ucvlPawnPiecesAttacking[sq] = self.pst[BLACK][KING][sq]
                self.ucvlPawnPiecesAttackless[sq] =  (cucvlKingPawnMidgameAttackless[sq] * nMidgameValue + cucvlKingPawnEndgameAttackless[sq] * (66 - nMidgameValue)) //66
                self.pst[RED][KING][SQUARES_180[sq]] = -self.pst[BLACK][KING][sq]
                self.pst[RED][KNIGHT][SQUARES_180[sq]] = -self.pst[BLACK][KNIGHT][sq]
                self.pst[RED][ROOK][SQUARES_180[sq]] = -self.pst[BLACK][ROOK][sq]
                self.pst[RED][CANNON][SQUARES_180[sq]] = -self.pst[BLACK][CANNON][sq]

        
        nRedAttacks = 2*count_ones((self.rooks|self.knights)&self.occupied_co[RED]&BB_BLACK_SIDE) + count_ones((self.cannons|self.pawns)&self.occupied_co[RED]&BB_BLACK_SIDE)
        nBlackAttacks = 2*count_ones((self.rooks|self.knights)&self.occupied_co[BLACK]&BB_RED_SIDE) + count_ones((self.cannons|self.pawns)&self.occupied_co[BLACK]&BB_RED_SIDE)

        nRedSimpleValue = 2*count_ones(self.rooks&self.occupied_co[RED]) + count_ones((self.knights|self.cannons)&self.occupied_co[RED])
        nBlackSimpleValue = 2*count_ones(self.rooks&self.occupied_co[BLACK]) + count_ones((self.knights|self.cannons)&self.occupied_co[BLACK])
        if (nRedSimpleValue > nBlackSimpleValue): nRedAttacks += (nRedSimpleValue - nBlackSimpleValue) * 2
        else: nBlackAttacks += (nBlackSimpleValue - nRedSimpleValue) * 2
        nRedAttacks = min(nRedAttacks, 8)
        nBlackAttacks = min(nBlackAttacks, 8)

        self.vlBlackAdvisorLeakage = 10 * nRedAttacks
        self.vlRedAdvisorLeakage = 10 * nBlackAttacks

        for i in range(16):
            self.vlHollowThreat[i] = cvlHollowThreat[i] * (nMidgameValue + 66) // (66 * 2)
            self.vlCentralThreat[i] = cvlCentralThreat[i]
            self.vlRedBottomThreat[i] = cvlBottomThreat[i] * nBlackAttacks // 8
            self.vlBlackBottomThreat[i] = cvlBottomThreat[i] * nRedAttacks // 8

        for sq in range(256):
            if (cucvlKnightEndgame[sq]):
                self.pst[RED][ADVISOR][sq] = self.pst[RED][BISHOP][sq] = -(cucvlAdvisorBishopThreatened[SQUARES_180[sq]] * nBlackAttacks + cucvlAdvisorBishopThreatless[SQUARES_180[sq]] * (8 - nBlackAttacks)) // 8

                self.pst[BLACK][ADVISOR][sq] = self.pst[BLACK][BISHOP][sq] = (cucvlAdvisorBishopThreatened[sq] * nRedAttacks +cucvlAdvisorBishopThreatless[sq] * (8 - nRedAttacks)) // 8
                
                self.pst[RED][PAWN][sq] = -(self.ucvlPawnPiecesAttacking[SQUARES_180[sq]] * nRedAttacks + self.ucvlPawnPiecesAttackless[SQUARES_180[sq]] * (8 - nRedAttacks)) // 8
                self.pst[BLACK][PAWN][sq] = (self.ucvlPawnPiecesAttacking[sq] * nBlackAttacks + self.ucvlPawnPiecesAttackless[sq] * (8 - nBlackAttacks)) // 8

        vl = 10 * (nBlackAttacks - nRedAttacks)
        
        for sq in scan_reversed(self.occupied):
            piece = self.piece_at(sq)
            vl += self.pst[piece.color][piece.piece_type][sq]
            self.key ^= zobrist[piece.color][piece.piece_type][sq]


        return vl


    def evaluate(self) -> int:
        vl = self.score
        # 以下是第一部分，特殊棋型的评价
        # 反向优化，心累-_-

        # vlRedPenalty = vlBlackPenalty = 0
        # if (count_ones(self.advisors & self.occupied_co[BLACK]) == 2):
        #     if (self.kings & BB_E9):
        #         sqadv = self.advisors & self.occupied_co[BLACK]
        #         sqAdv1 = sqadv.bit_length() - 1
        #         sqadv ^= BB_SQUARES[sqAdv1]
        #         sqAdv2 = sqadv.bit_length() - 1
        #         nShape = 0
        #         if (sqAdv1 == 0xc6): 
        #             nShape = 1 if sqAdv2 == 0xc8 else  (2 if sqAdv2 == 0xb7 else 0)
        #         elif (sqAdv1 == 0xc8):
        #             nShape = 1 if sqAdv2 == 0xc6 else  (3 if sqAdv2 == 0xb7 else 0)
        #         elif (sqAdv1 == 0xb7):
        #             nShape = 2 if sqAdv2 == 0xc6 else  (3 if sqAdv2 == 0xc8 else 0)
        #         if(nShape):
        #             if(nShape == 1):
        #                 for sq in scan_reversed(self.occupied_co[RED]&self.cannons):
        #                     if (sq&0xf) == 7:
        #                         mask = between(0xc7, sq)
        #                         b = mask & self.occupied
        #                         # 炮镇窝心马
        #                         if count_ones(b) == 2 and self.knights & self.occupied_co[BLACK] & BB_E8:
        #                             vlBlackPenalty += self.vlCentralThreat[sq>>4]
        #                         # 空头炮
        #                         elif count_ones(b) == 0:
        #                             vlBlackPenalty += self.vlHollowThreat[sq>>4]
        #             else:
        #                 for sq in scan_reversed(self.occupied_co[RED]&self.cannons):
        #                     if (sq&0xf) == 7:
        #                         mask = between(0xc7, sq)
        #                         b = mask & self.occupied
        #                         if count_ones(b) == 2 :
        #                             vlBlackPenalty += self.vlCentralThreat[sq>>4] >> 2
        #                             for sq in scan_reversed(self.occupied_co[BLACK]&self.rooks):
        #                                 if (sq>>4) == 0xc and count_ones(between(0xc7, sq)) == 0:
        #                                     vlBlackPenalty += 80
        #                     elif (sq>>4) == 0xc and count_ones(between(0xc7, sq)) == 0:
        #                         vlBlackPenalty += self.vlBlackBottomThreat[sq&0xf]
        #     elif (self.kings & BB_E8):
        #         vlBlackPenalty += 20
        # elif (count_ones(self.rooks & self.occupied_co[RED]) == 2):
        #     vlBlackPenalty += self.vlBlackAdvisorLeakage


        # if (count_ones(self.advisors & self.occupied_co[RED]) == 2):
        #     if (self.kings & BB_E0):
        #         sqadv = self.advisors & self.occupied_co[RED]
        #         sqAdv1 = sqadv.bit_length() - 1
        #         sqadv ^= BB_SQUARES[sqAdv1]
        #         sqAdv2 = sqadv.bit_length() - 1
        #         nShape = 0
        #         if (sqAdv1 == 0x36): 
        #             nShape = 1 if sqAdv2 == 0x38 else  (2 if sqAdv2 == 0x47 else 0)
        #         elif (sqAdv1 == 0x38):
        #             nShape = 1 if sqAdv2 == 0x36 else  (3 if sqAdv2 == 0x47 else 0)
        #         elif (sqAdv1 == 0x47):
        #             nShape = 2 if sqAdv2 == 0x36 else  (3 if sqAdv2 == 0x38 else 0)
        #         if(nShape):
        #             if(nShape == 1):
        #                 for sq in scan_reversed(self.occupied_co[BLACK]&self.cannons):
        #                     if (sq&0xf) == 7:
        #                         mask = between(0x37, sq)
        #                         b = mask & self.occupied
        #                         # 炮镇窝心马
        #                         if count_ones(b) == 2 and self.knights & self.occupied_co[RED] & BB_E2:
        #                             vlRedPenalty += self.vlCentralThreat[15-(sq>>4)]
        #                         # 空头炮
        #                         elif count_ones(b) == 0:
        #                             vlRedPenalty += self.vlHollowThreat[15-(sq>>4)]
        #             else:
        #                 for sq in scan_reversed(self.occupied_co[BLACK]&self.cannons):
        #                     if (sq&0xf) == 7:
        #                         mask = between(0xc7, sq)
        #                         b = mask & self.occupied
        #                         if count_ones(b) == 2 :
        #                             vlRedPenalty += self.vlCentralThreat[15-(sq>>4)] >> 2
        #                             for sq in scan_reversed(self.occupied_co[RED]&self.rooks):
        #                                 if (sq>>4) == 0x3 and count_ones(between(0x37, sq)) == 0:
        #                                     vlRedPenalty += 80
        #                     elif (sq>>4) == 0x3 and count_ones(between(0x37, sq)) == 0:
        #                         vlRedPenalty += self.vlRedBottomThreat[sq&0xf]
        #     elif (self.kings & BB_E2):
        #         vlRedPenalty += 20
        # elif (count_ones(self.rooks & self.occupied_co[BLACK]) == 2):
        #     vlRedPenalty += self.vlRedAdvisorLeakage
        # vl += vlRedPenalty - vlBlackPenalty

        #以下是第二部分，牵制(保护)的评价
        #to be continue

        # 以下是第三部分，车的灵活性的评价
        # vlability = [0,0]
        # for color in (RED,BLACK):
        #     for sq in scan_reversed(self.occupied_co[color]&self.rooks):
        #         vlability[color] += (self.attacks_mask(sq)&(~self.occupied))
        # vl += (vlability[BLACK] - vlability[RED] )>>1

        
        # 以下是第四部分，马受到阻碍的评价
        #to be continue

        return vl







    def _remove_piece_at(self, square: Square) -> Optional[PieceType]:
        piece_type = self.piece_type_at(square)
        mask = BB_SQUARES[square]

        if piece_type == PAWN:
            self.pawns ^= mask
        elif piece_type == KNIGHT:
            self.knights ^= mask
        elif piece_type == BISHOP:
            self.bishops ^= mask
        elif piece_type == ROOK:
            self.rooks ^= mask
        elif piece_type == CANNON:
            self.cannons ^= mask
        elif piece_type == KING:
            self.kings ^= mask
        elif piece_type == ADVISOR:
            self.advisors ^= mask
        else:
            return None

        self.occupied ^= mask
        self.occupied_co[RED] &= ~mask
        self.occupied_co[BLACK] &= ~mask

        return piece_type

    def remove_piece_at(self, square: Square) -> Optional[Piece]:
        color = bool(self.occupied_co[RED] & BB_SQUARES[square])
        piece_type = self._remove_piece_at(square)
        return Piece(piece_type, color) if piece_type else None

    def _set_piece_at(self, square: Square, piece_type: PieceType, color: Color) -> None:
        self._remove_piece_at(square)

        mask = BB_SQUARES[square]

        if piece_type == PAWN:
            self.pawns |= mask
        elif piece_type == KNIGHT:
            self.knights |= mask
        elif piece_type == BISHOP:
            self.bishops |= mask
        elif piece_type == ROOK:
            self.rooks |= mask
        elif piece_type == CANNON:
            self.cannons |= mask
        elif piece_type == KING:
            self.kings |= mask
        elif piece_type == ADVISOR:
            self.advisors |= mask
        else:
            return

        self.occupied ^= mask
        self.occupied_co[color] ^= mask

    def set_piece_at(self, square: Square, piece: Optional[Piece]) -> None:
        if piece is None:
            self._remove_piece_at(square)
        else:
            self._set_piece_at(square, piece.piece_type, piece.color)

    def piece_at(self, square: Square) -> Optional[Piece]:
        piece_type = self.piece_type_at(square)
        if piece_type:
            mask = BB_SQUARES[square]
            color = bool(self.occupied_co[RED] & mask)
            return Piece(piece_type, color)
        else:
            return None

    def piece_type_at(self, square: Square) -> Optional[PieceType]:
        mask = BB_SQUARES[square]
        if not self.occupied & mask:
            return None
        elif self.pawns & mask:
            return PAWN
        elif self.knights & mask:
            return KNIGHT
        elif self.bishops & mask:
            return BISHOP
        elif self.rooks & mask:
            return ROOK
        elif self.cannons & mask:
            return CANNON
        elif self.advisors & mask:
            return ADVISOR
        else:
            return KING

    def color_at(self, square: Square) -> Optional[Color]:
        mask = BB_SQUARES[square]
        if self.occupied_co[RED] & mask:
            return RED
        elif self.occupied_co[BLACK] & mask:
            return BLACK
        else:
            return None

    def king(self, color: Color) -> Optional[Square]:
        king_mask = self.occupied_co[color] & self.kings
        return msb(king_mask) if king_mask else None

    def attacks_mask(self, square: Square) -> Bitboard:
        bb_square = BB_SQUARES[square]

        if bb_square & self.pawns:
            color = bool(bb_square & self.occupied_co[RED])
            return BB_PAWN_ATTACKS[color][square]
        if bb_square & self.kings:
            # 老将对脸杀
            return BB_KING_ATTACKS[square] | ((BB_FILE_ATTACKS[square][BB_FILE_MASKS[square] & self.occupied] |
                                               BB_RANK_ATTACKS[square][BB_RANK_MASKS[square] & self.occupied]) & self.kings)
        if bb_square & self.advisors:
            return BB_ADVISOR_ATTACKS[square]
        elif bb_square & self.knights:
            return BB_KNIGHT_ATTACKS[square][BB_KNIGHT_MASKS[square] & self.occupied]
        elif bb_square & self.bishops:
            return BB_BISHOP_ATTACKS[square][BB_BISHOP_MASKS[square] & self.occupied]
        elif bb_square & self.rooks:
            return (BB_FILE_ATTACKS[square][BB_FILE_MASKS[square] & self.occupied] |
                    BB_RANK_ATTACKS[square][BB_RANK_MASKS[square] & self.occupied])
        elif bb_square & self.cannons:
            return (BB_CANNON_FILE_ATTACKS[square][BB_CANNON_FILE_MASKS[square] & self.occupied] |
                    BB_CANNON_RANK_ATTACKS[square][BB_CANNON_RANK_MASKS[square] & self.occupied] |
                    ((BB_FILE_ATTACKS[square][BB_FILE_MASKS[square] & self.occupied] |
                      BB_RANK_ATTACKS[square][BB_RANK_MASKS[square] & self.occupied]) & ~self.occupied))
        else:
            return BB_EMPTY

    def _attackers_mask(self, color: Color, square: Square, occupied: Bitboard) -> Bitboard:
        cannon_attacks = (BB_CANNON_FILE_ATTACKS[square][BB_CANNON_FILE_MASKS[square] & occupied] |
                          BB_CANNON_RANK_ATTACKS[square][BB_CANNON_RANK_MASKS[square] & occupied])
        rook_attacks = (BB_FILE_ATTACKS[square][BB_FILE_MASKS[square] & occupied] |
                        BB_RANK_ATTACKS[square][BB_RANK_MASKS[square] & occupied])
        attackers = (
            (cannon_attacks & self.cannons) |
            (rook_attacks & self.rooks) |
            (BB_KNIGHT_REVERSED_ATTACKS[square][occupied & BB_KNIGHT_REVERSED_MASKS[square]] & self.knights) |
            (BB_BISHOP_ATTACKS[square][occupied & BB_BISHOP_MASKS[square]] & self.bishops) |
            (BB_PAWN_REVERSED_ATTACKS[color][square] & self.pawns) |
            (BB_ADVISOR_ATTACKS[square] & self.advisors) |
            ((BB_KING_ATTACKS[square] | (rook_attacks & self.kings)) & self.kings)
        )
        return attackers & self.occupied_co[color]

    def attackers_mask(self, color: Color, square: Square) -> Bitboard:
        return self._attackers_mask(color, square, self.occupied)

    def is_attacked_by(self, color: Color, square: Square) -> bool:
        return bool(self.attackers_mask(color, square))


    def checkers_mask(self) -> Bitboard:
        king = self.king(self.turn)
        return BB_EMPTY if king is None else self.attackers_mask(not self.turn, king)

    def _is_safe(self, king: Square, slider_blockers: List[Tuple[Bitboard, Bitboard]],
                 knight_blockers: List[Tuple[Bitboard, Bitboard]]
                 , move: Move) -> bool:

        if move.from_square == king:
            # 把将去掉
            return not bool(self._attackers_mask(not self.turn, move.to_square, self.occupied & ~BB_SQUARES[king]))

        bb_from = BB_SQUARES[move.from_square]
        bb_to = BB_SQUARES[move.to_square]

        for blocker, to in knight_blockers:
            # 如果正在移动马腿棋子
            if blocker & bb_from and (not bb_to & to):
                return False

        for mask, sniper, limit in slider_blockers:
            # 如果正在移动阻挡棋子
            if mask & bb_from or mask & bb_to:
                if not (sniper & bb_to) and count_ones(self.occupied & mask & ~bb_from | bb_to & mask) == limit:
                    return False

        return True

    def is_pseudo_legal(self, move: Move) -> bool:
        if not move:
            return False
        # 必须有棋子
        piece = self.piece_type_at(move.from_square)
        if not piece:
            return False

        from_mask = BB_SQUARES[move.from_square]
        to_mask = BB_SQUARES[move.to_square]

        # 是否是自己的棋子
        if not self.occupied_co[self.turn] & from_mask:
            return False

        # 目标格子不能有自己的棋子
        if self.occupied_co[self.turn] & to_mask:
            return False

        return bool(self.attacks_mask(move.from_square) & to_mask)

    def is_legal(self, move: Move) -> bool:
        return self.is_pseudo_legal(move) and not self.is_into_check(move)

    def is_into_check(self, move: Move) -> bool:
        king = self.king(self.turn)
        if king is None:
            return False

        checkers = self.attackers_mask(not self.turn, king)
        if checkers and move not in self._generate_evasions(king, checkers, BB_SQUARES[move.from_square], BB_SQUARES[move.to_square]):
            return True

        return not self._is_safe(king, self._slider_blockers(king), self._knight_blockers(king), move)

    def _slider_blockers(self, king: Square) -> List[Tuple[Bitboard, Bitboard, int]]:
        rays = (BB_FILE_ATTACKS[king][BB_EMPTY] | BB_RANK_ATTACKS[king][BB_EMPTY])
        cannons = rays & self.cannons & self.occupied_co[not self.turn]
        rooks_and_kings = rays & (self.kings | self.rooks) & self.occupied_co[not self.turn]

        blockers = []

        for sniper in scan_reversed(cannons):
            mask = between(king, sniper)
            b = count_ones(mask & self.occupied)
            # 如果路线上只有两个棋子
            if b == 2:
                blockers.append((mask, BB_SQUARES[sniper], 1))
            # 空头炮
            elif b == 0:
                blockers.append((mask, BB_SQUARES[sniper], 1))

        for sniper in scan_reversed(rooks_and_kings):
            mask = between(king, sniper)
            b = mask & self.occupied
            # 如果路线上只有一个棋子则是一个 blocker
            if b and count_ones(b) == 1:
                blockers.append((mask, BB_SQUARES[sniper], 0))

        return blockers

    def _knight_blockers(self, king: Square) -> List[Tuple[Bitboard, Bitboard]]:
        # 生成正在别马脚的棋子
        knights = self.knights & self.occupied_co[not self.turn]
        blockers = BB_EMPTY
        blockers_detail = []
        occupied = BB_KNIGHT_REVERSED_MASKS[king] & self.occupied_co[self.turn]
        masks = [BB_KNIGHT_REVERSED_MASKS[king] & ~BB_SQUARES[king + 15],
                 BB_KNIGHT_REVERSED_MASKS[king] & ~BB_SQUARES[king + 17],
                 BB_KNIGHT_REVERSED_MASKS[king] & ~BB_SQUARES[king - 15],
                 BB_KNIGHT_REVERSED_MASKS[king] & ~BB_SQUARES[king - 17],
                 ]
        for mask in masks:
            attack_knights = BB_KNIGHT_REVERSED_ATTACKS[king][mask] & knights
            if attack_knights and (occupied & ~mask):
                blockers |= (occupied & ~mask)
                if count_ones(attack_knights) == 1:
                    blockers_detail.append((occupied & ~mask, attack_knights))
                else:
                    blockers_detail.append((occupied & ~mask, BB_EMPTY))

        return blockers_detail

    def _generate_evasions(self, king: Square, checkers: Bitboard,
                           from_mask: Bitboard = BB_IN_BOARD, to_mask: Bitboard = BB_IN_BOARD) -> Iterator[Move]:

        attacked = BB_EMPTY
        for checker in scan_reversed(checkers & self.rooks):
            attacked |= line(king, checker) & ~BB_SQUARES[checker]

        for checker in scan_reversed(checkers & self.cannons):
            middle = between(king, checker) & self.occupied
            l = between(middle, checker) | middle
            attacked |= line(king, checker) & ~l & ~BB_SQUARES[checker]

        if BB_SQUARES[king] & from_mask:
            for to_square in scan_reversed(BB_KING_ATTACKS[king] & ~self.occupied_co[self.turn] & ~attacked & to_mask):
                yield Move(king, to_square)

        ones_number = count_ones(checkers)
        if ones_number == 1:
            # 只有一个子将
            checker = msb(checkers)
            # 将军?只是假象!
            yield from self.generate_pseudo_legal_moves(~self.kings & from_mask, checkers & to_mask)
            if checkers & (self.rooks | self.kings | self.pawns):
                target = between(king, checker)
                yield from self.generate_pseudo_legal_moves(~self.kings & from_mask, target & to_mask)
            elif checkers & self.cannons:
                target = between(king, checker) | checkers
                # 垫子但不能吃子
                yield from self.generate_pseudo_legal_moves(~self.kings & from_mask & ~target, target & to_mask & ~self.occupied)
                # 拆炮架
                yield from self.generate_pseudo_legal_moves(~self.kings & from_mask & target, ~target & to_mask)
            elif checkers & self.knights:
                # 别马腿
                yield from self.generate_pseudo_legal_moves(~self.kings & from_mask, _knight_blocker(king, checker) & to_mask)
                

        elif ones_number == 2:
            # 车炮双将
            cannon_checker = msb(checkers & self.cannons)
            rook_checker = msb(checkers & self.rooks)
            if line(cannon_checker, rook_checker) & BB_SQUARES[king] and not (between(cannon_checker, rook_checker) & BB_SQUARES[king]):
                yield from self.generate_pseudo_legal_moves(~self.kings & from_mask, between(king, rook_checker) & to_mask)

    def generate_pseudo_legal_moves(self, from_mask: Bitboard = BB_IN_BOARD, to_mask: Bitboard = BB_IN_BOARD) -> Iterator[Move]:
        our_pieces = self.occupied_co[self.turn]

        from_squares = our_pieces & from_mask
        for from_square in scan_reversed(from_squares):
            moves = self.attacks_mask(from_square) & ~our_pieces & to_mask
            for to_square in scan_reversed(moves):
                yield Move(from_square, to_square)

    def generate_legal_moves(self, from_mask: Bitboard = BB_IN_BOARD, to_mask: Bitboard = BB_IN_BOARD) -> Iterator[Move]:
        king_mask = self.kings & self.occupied_co[self.turn]
        if king_mask:
            king = msb(king_mask)
            slider_blockers = self._slider_blockers(king)
            knight_blockers = self._knight_blockers(king)
            checkers = self.attackers_mask(not self.turn, king)
            if checkers:
                for move in self._generate_evasions(king, checkers, from_mask, to_mask):
                    if self._is_safe(king, slider_blockers, knight_blockers, move):
                        yield move
            else:
                swap =  to_mask & self.occupied_co[not self.turn]
                for move in self.generate_pseudo_legal_moves(from_mask,swap):
                    if self._is_safe(king, slider_blockers, knight_blockers, move):
                        yield move
                for move in self.generate_pseudo_legal_moves(from_mask, to_mask ^ swap):
                    if self._is_safe(king, slider_blockers, knight_blockers, move):
                        yield move
        else:
            yield from self.generate_pseudo_legal_moves(from_mask, to_mask)

